from __future__ import annotations

import pytest

from ml_research.io import read_json


def test_read_json_rejects_duplicate_object_keys(tmp_path) -> None:
    candidate = tmp_path / "candidate.json"
    candidate.write_text('{"version": 1, "version": 2}\n', encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate JSON object key: version"):
        read_json(candidate)
