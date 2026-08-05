from __future__ import annotations

import re
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

ShortText = Annotated[str, Field(min_length=8, max_length=240)]
Paragraph = Annotated[str, Field(min_length=60, max_length=2400)]
ListItem = Annotated[str, Field(min_length=20, max_length=600)]

ARXIV_ID_RE = re.compile(r"^(?:[a-z-]+/\d{7}|\d{4}\.\d{4,5})(?:v\d+)?$", re.I)


class PaperDigest(BaseModel):
    """One primary-source-backed paper recommendation."""

    model_config = ConfigDict(extra="forbid")

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

        paper_url = str(self.paperUrl)
        pdf_url = str(self.pdfUrl)
        if "arxiv.org/abs/" not in paper_url:
            raise ValueError("paperUrl must be an arxiv.org abstract URL")
        if "arxiv.org/pdf/" not in pdf_url:
            raise ValueError("pdfUrl must be an arxiv.org PDF URL")
        if self.arxivId.removesuffix("v1") not in paper_url:
            normalized = re.sub(r"v\d+$", "", self.arxivId)
            if normalized not in paper_url:
                raise ValueError("paperUrl does not match arxivId")

        sources = {str(url) for url in self.sourceUrls}
        if paper_url not in sources:
            raise ValueError("sourceUrls must include paperUrl")
        if len(self.keyFindingsKo) != len(self.keyFindingsEn):
            raise ValueError("Korean and English key findings must align")
        if len(self.limitationsKo) != len(self.limitationsEn):
            raise ValueError("Korean and English limitations must align")
        return self


class WeeklyDigest(BaseModel):
    """One bilingual public weekly digest containing three to five papers."""

    model_config = ConfigDict(extra="forbid")

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


class DigestArchive(BaseModel):
    """Versioned document consumed directly by HYOYOUL BLOG."""

    model_config = ConfigDict(extra="forbid")

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
