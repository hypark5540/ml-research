from __future__ import annotations

import json

import pytest

from ml_research.models import WeeklyDigest
from scripts.publish_digest import append_digest
from tests.test_models import sample_digest


def test_append_digest_creates_archive(tmp_path) -> None:
    target = tmp_path / "archive.json"
    digest = WeeklyDigest.model_validate(sample_digest())

    archive = append_digest(digest, target)

    assert archive.digests[0].id == digest.id
    assert json.loads(target.read_text())["digests"][0]["id"] == digest.id


def test_append_digest_rejects_same_week(tmp_path) -> None:
    target = tmp_path / "archive.json"
    digest = WeeklyDigest.model_validate(sample_digest())
    append_digest(digest, target)

    with pytest.raises(ValueError, match="already exists"):
        append_digest(digest, target)
