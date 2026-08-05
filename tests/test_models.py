from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

from ml_research.models import DigestArchive, WeeklyDigest


def sample_digest() -> dict:
    paper = {
        "arxivId": "2608.01234",
        "title": "A Carefully Evaluated Machine Learning System",
        "authors": ["A. Researcher", "B. Engineer"],
        "publishedAt": "2026-08-01",
        "venue": None,
        "paperUrl": "https://arxiv.org/abs/2608.01234",
        "pdfUrl": "https://arxiv.org/pdf/2608.01234",
        "huggingFaceUrl": "https://huggingface.co/papers/2608.01234",
        "codeUrl": "https://github.com/example/research",
        "summaryKo": "이 연구는 운영 환경의 머신러닝 시스템을 대상으로 재현 가능한 평가 절차와 데이터 품질 검증 방법을 비교하고 결과를 보고합니다.",
        "summaryEn": "This study compares reproducible evaluation procedures and data-quality checks for production machine-learning systems and reports the resulting measurements.",
        "whyRecommendedKo": "모델 점수만 보지 않고 데이터 계약과 운영 검증을 함께 다루므로 데이터 엔지니어가 실제 시스템에 적용할 연결점이 분명합니다.",
        "whyRecommendedEn": "It connects model evaluation with data contracts and operational checks, giving data engineers concrete ideas that transfer to real systems.",
        "keyFindingsKo": [
            "동일한 입력 계약을 사용하면 학습과 서빙 사이의 불일치를 더 이른 단계에서 탐지할 수 있습니다.",
            "평균 점수와 함께 실패 구간을 분리해서 보고해야 운영 위험을 숨기지 않을 수 있습니다.",
        ],
        "keyFindingsEn": [
            "A shared input contract detects training-serving mismatches earlier in the pipeline.",
            "Reporting failure slices beside averages avoids hiding important operational risk.",
        ],
        "limitationsKo": [
            "제한된 데이터셋과 워크로드에서 평가되어 다른 도메인으로의 일반화는 추가 검증이 필요합니다."
        ],
        "limitationsEn": [
            "The evaluation uses a limited set of datasets and workloads, so other domains need additional validation."
        ],
        "sourceUrls": [
            "https://arxiv.org/abs/2608.01234",
            "https://github.com/example/research",
        ],
    }
    papers = []
    for index in range(3):
        item = deepcopy(paper)
        item["arxivId"] = f"2608.{1234 + index:05d}"
        item["paperUrl"] = f"https://arxiv.org/abs/{item['arxivId']}"
        item["pdfUrl"] = f"https://arxiv.org/pdf/{item['arxivId']}"
        item["huggingFaceUrl"] = f"https://huggingface.co/papers/{item['arxivId']}"
        item["sourceUrls"][0] = item["paperUrl"]
        papers.append(item)

    return {
        "version": 1,
        "id": "research-2026-08-06",
        "slug": "weekly-ml-research-digest-2026-08-06",
        "weekOf": "2026-08-06",
        "generatedAt": "2026-08-06T09:00:00+09:00",
        "titleKo": "이번 주에 읽을 머신러닝 시스템 연구 3편",
        "titleEn": "Three Machine Learning Systems Papers to Read This Week",
        "excerptKo": "운영 머신러닝과 데이터 품질, 에이전트 평가를 연결해 이번 주에 읽을 연구 세 편과 실무적인 의미를 정리합니다.",
        "excerptEn": "A weekly selection connecting production ML, data quality, and agent evaluation, with practical notes on why each paper matters.",
        "editorNoteKo": "이번 주에는 단기 성능 수치보다 재현 가능한 평가와 운영 시스템에 옮길 수 있는 방법론을 우선해 세 편을 골랐습니다.",
        "editorNoteEn": "This week prioritizes reproducible evaluation and methods that transfer to operating systems over isolated headline scores.",
        "tagsKo": ["머신러닝", "ML 시스템", "논문"],
        "tagsEn": ["Machine Learning", "ML Systems", "Papers"],
        "readTime": 10,
        "papers": papers,
    }


def test_valid_weekly_digest() -> None:
    digest = WeeklyDigest.model_validate(sample_digest())
    assert len(digest.papers) == 3


def test_rejects_mismatched_identity() -> None:
    payload = sample_digest()
    payload["id"] = "research-wrong"
    with pytest.raises(ValidationError, match="id must be"):
        WeeklyDigest.model_validate(payload)


def test_archive_rejects_repeated_paper() -> None:
    first = sample_digest()
    second = deepcopy(first)
    second["id"] = "research-2026-08-13"
    second["slug"] = "weekly-ml-research-digest-2026-08-13"
    second["weekOf"] = "2026-08-13"
    with pytest.raises(ValidationError, match="already appears"):
        DigestArchive.model_validate({"version": 1, "digests": [first, second]})
