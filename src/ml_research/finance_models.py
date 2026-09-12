from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Metric(StrictModel):
    labelKo: str
    labelEn: str
    value: str
    unit: str
    basis: Literal["GAAP", "non-GAAP", "operating"]
    period: str


class Review(StrictModel):
    company: str
    ticker: str
    releaseDate: str
    fiscalPeriod: str
    sourceUrl: str
    metrics: list[Metric] = Field(min_length=3, max_length=6)
    summaryKo: str
    summaryEn: str
    interpretationKo: str
    interpretationEn: str
    risksKo: list[str] = Field(min_length=2, max_length=4)
    risksEn: list[str] = Field(min_length=2, max_length=4)
    watchKo: str
    watchEn: str


class Preview(StrictModel):
    company: str
    ticker: str
    eventDate: str
    eventType: Literal["earnings", "investor-event"]
    timeEt: str
    sourceUrl: str
    watchKo: str
    watchEn: str


class Digest(StrictModel):
    version: Literal[1]
    id: str
    slug: str
    weekOf: str
    generatedAt: str
    titleKo: str
    titleEn: str
    excerptKo: str
    excerptEn: str
    editorNoteKo: str
    editorNoteEn: str
    reviews: list[Review] = Field(min_length=1, max_length=5)
    preview: list[Preview] = Field(max_length=5)
    coverageNoteKo: str
    coverageNoteEn: str
    readTime: int
