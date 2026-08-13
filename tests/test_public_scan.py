from __future__ import annotations

import pytest

from ml_research.public_scan import assert_public_text_has_no_secret, find_public_secret


@pytest.mark.parametrize(
    "value",
    [
        "hf_" + "a" * 30,
        "github_" + "pat_" + "a" * 44,
        "ghp_" + "a" * 36,
        "glpat-" + "a" * 30,
        "sk-" + "proj-" + "a" * 30,
        "AKIA" + "A" * 16,
        "AIza" + "a" * 35,
        "xox" + "b-" + "1" * 12 + "-" + "a" * 30,
        "npm_" + "a" * 36,
        "-----BEGIN PRIVATE KEY-----",
    ],
)
def test_detects_credential_shaped_public_values(value: str) -> None:
    assert find_public_secret(f"prefix {value} suffix") is not None


def test_detects_exact_protected_secret(monkeypatch) -> None:
    monkeypatch.setenv("HF_TOKEN", "opaque-value-not-matching-a-known-prefix")
    with pytest.raises(ValueError, match="exact protected secret"):
        assert_public_text_has_no_secret("opaque-value-not-matching-a-known-prefix")
