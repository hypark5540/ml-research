from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

ShortText = Annotated[str, Field(min_length=8, max_length=240)]
Paragraph = Annotated[str, Field(min_length=60, max_length=2400)]
ListItem = Annotated[str, Field(min_length=20, max_length=600)]

ARXIV_ID_RE = re.compile(r"^(?:[a-z-]+/\d{7}|\d{4}\.\d{4,5})(?:v\d+)?$", re.I)
FORBIDDEN_PUBLIC_TEXT_RE = re.compile(
    r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\u200b-\u200d\u202a-\u202e"
    r"\u2060\u2066-\u2069\ufeff\ufffd]"
)
ARXIV_HOSTS = frozenset({"arxiv.org"})
HUGGING_FACE_HOSTS = frozenset({"huggingface.co"})
CODE_HOSTS = frozenset({"github.com", "gitlab.com", "bitbucket.org", "codeberg.org"})
SOURCE_HOSTS = frozenset(
    {
        *ARXIV_HOSTS,
        *HUGGING_FACE_HOSTS,
        *CODE_HOSTS,
        "doi.org",
        "openreview.net",
        "aclanthology.org",
        "proceedings.mlr.press",
    }
)


def iter_public_strings(value: object, path: str = "$") -> Iterator[tuple[str, str]]:
    """Yield every public string with a stable path for actionable validation errors."""

    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from iter_public_strings(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            yield from iter_public_strings(item, f"{path}[{index}]")


def normalized_host(url: HttpUrl) -> str:
    return (url.host or "").lower().rstrip(".").removeprefix("www.")


def validate_trusted_url(
    url: HttpUrl, allowed_hosts: frozenset[str], label: str
) -> None:
    host = normalized_host(url)
    if url.scheme != "https":
        raise ValueError(f"{label} must use HTTPS")
    if host not in allowed_hosts:
        raise ValueError(f"{label} uses an untrusted host: {host}")
    if url.username or url.password:
        raise ValueError(f"{label} must not include URL credentials")
    if url.port != 443:
        raise ValueError(f"{label} must use the default HTTPS port")
    if url.query or url.fragment:
        raise ValueError(f"{label} must not include a query string or fragment")


class PublicContentModel(BaseModel):
    """Strict base model for content that will be rendered on the public blog."""

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def reject_unsafe_public_text(cls, value: object) -> object:
        for path, text in iter_public_strings(value):
            match = FORBIDDEN_PUBLIC_TEXT_RE.search(text)
            if match:
                codepoint = f"U+{ord(match.group()):04X}"
                raise ValueError(
                    f"forbidden public-text character {codepoint} at {path}"
                )
        return value


class PaperDigest(PublicContentModel):
    """One primary-source-backed paper recommendation."""

    arxivId: str
    title: ShortText
    authors: list[Annotated[str, Field(min_length=2, max_length=120)]] = Field(
        min_length=1, max_length=30
    )
    publishedAt: date
    venue: Annotated[str, Field(max_length=160)] | None = None
    paperUrl: HttpUrl
    pdfUrl: HttpUrl
    huggingFaceUrl: HttpUrl | None = None
    codeUrl: HttpUrl | None = None
    summaryKo: Paragraph
    summaryEn: Paragraph
    whyRecommendedKo: Paragraph
    whyRecommendedEn: Paragraph
    keyFindingsKo: list[ListItem] = Field(min_length=2, max_length=5)
    keyFindingsEn: list[ListItem] = Field(min_length=2, max_length=5)
    limitationsKo: list[ListItem] = Field(min_length=1, max_length=4)
    limitationsEn: list[ListItem] = Field(min_length=1, max_length=4)
    sourceUrls: list[HttpUrl] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def validate_primary_sources(self) -> PaperDigest:
        if not ARXIV_ID_RE.fullmatch(self.arxivId):
            raise ValueError(f"invalid arXiv id: {self.arxivId}")

        normalized_id = re.sub(r"v\d+$", "", self.arxivId, flags=re.I)
        validate_trusted_url(self.paperUrl, ARXIV_HOSTS, "paperUrl")
        validate_trusted_url(self.pdfUrl, ARXIV_HOSTS, "pdfUrl")
        if self.huggingFaceUrl:
            validate_trusted_url(
                self.huggingFaceUrl, HUGGING_FACE_HOSTS, "huggingFaceUrl"
            )
        if self.codeUrl:
            validate_trusted_url(self.codeUrl, CODE_HOSTS, "codeUrl")
        for source_url in self.sourceUrls:
            validate_trusted_url(source_url, SOURCE_HOSTS, "sourceUrls entry")

        paper_url = str(self.paperUrl)
        paper_path = self.paperUrl.path.rstrip("/")
        pdf_path = self.pdfUrl.path.rstrip("/")
        versioned_id = rf"{re.escape(normalized_id)}(?:v\d+)?"
        if not re.fullmatch(rf"/abs/{versioned_id}", paper_path, flags=re.I):
            raise ValueError("paperUrl must be the matching arxiv.org abstract URL")
        if not re.fullmatch(rf"/pdf/{versioned_id}(?:\.pdf)?", pdf_path, flags=re.I):
            raise ValueError("pdfUrl must be the matching arxiv.org PDF URL")
        if self.huggingFaceUrl and not re.fullmatch(
            rf"/papers/{versioned_id}",
            self.huggingFaceUrl.path.rstrip("/"),
            flags=re.I,
        ):
            raise ValueError("huggingFaceUrl must match arxivId")

        for source_url in self.sourceUrls:
            if normalized_host(
                source_url
            ) == "arxiv.org" and normalized_id.lower() not in (source_url.path.lower()):
                raise ValueError("arXiv sourceUrls entries must match arxivId")

        sources = {str(url) for url in self.sourceUrls}
        if paper_url not in sources:
            raise ValueError("sourceUrls must include paperUrl")
        if len(self.keyFindingsKo) != len(self.keyFindingsEn):
            raise ValueError("Korean and English key findings must align")
        if len(self.limitationsKo) != len(self.limitationsEn):
            raise ValueError("Korean and English limitations must align")
        return self


class WeeklyDigest(PublicContentModel):
    """One bilingual public weekly digest containing three to five papers."""

    version: Literal[1] = 1
    id: str
    slug: str
    weekOf: date
    generatedAt: datetime
    titleKo: ShortText
    titleEn: ShortText
    excerptKo: Annotated[str, Field(min_length=60, max_length=320)]
    excerptEn: Annotated[str, Field(min_length=60, max_length=320)]
    editorNoteKo: Paragraph
    editorNoteEn: Paragraph
    tagsKo: list[Annotated[str, Field(min_length=2, max_length=40)]] = Field(
        min_length=2, max_length=8
    )
    tagsEn: list[Annotated[str, Field(min_length=2, max_length=40)]] = Field(
        min_length=2, max_length=8
    )
    readTime: int = Field(ge=6, le=30)
    papers: list[PaperDigest] = Field(min_length=3, max_length=5)

    @model_validator(mode="after")
    def validate_identity_and_bilingual_shape(self) -> WeeklyDigest:
        suffix = self.weekOf.isoformat()
        if self.id != f"research-{suffix}":
            raise ValueError(f"id must be research-{suffix}")
        if self.slug != f"weekly-ml-research-digest-{suffix}":
            raise ValueError(f"slug must be weekly-ml-research-digest-{suffix}")
        if len(self.tagsKo) != len(self.tagsEn):
            raise ValueError("Korean and English tags must align")

        paper_ids = [re.sub(r"v\d+$", "", paper.arxivId) for paper in self.papers]
        if len(set(paper_ids)) != len(paper_ids):
            raise ValueError("a digest cannot recommend the same arXiv paper twice")
        return self


class DigestArchive(PublicContentModel):
    """Versioned document consumed directly by HYOYOUL BLOG."""

    version: Literal[1] = 1
    digests: list[WeeklyDigest]

    @model_validator(mode="after")
    def validate_archive_uniqueness(self) -> DigestArchive:
        ids = [digest.id for digest in self.digests]
        slugs = [digest.slug for digest in self.digests]
        weeks = [digest.weekOf for digest in self.digests]
        if len(set(ids)) != len(ids):
            raise ValueError("digest ids must be unique")
        if len(set(slugs)) != len(slugs):
            raise ValueError("digest slugs must be unique")
        if len(set(weeks)) != len(weeks):
            raise ValueError("only one digest may be published per weekOf date")

        seen_papers: set[str] = set()
        for digest in self.digests:
            for paper in digest.papers:
                paper_id = re.sub(r"v\d+$", "", paper.arxivId)
                if paper_id in seen_papers:
                    raise ValueError(
                        f"arXiv paper {paper_id} already appears in another digest"
                    )
                seen_papers.add(paper_id)
        return self
