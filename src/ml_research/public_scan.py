from __future__ import annotations

import os
import re
from collections.abc import Iterable


PUBLIC_SECRET_PATTERNS = (
    re.compile(r"hf_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{40,}"),
    re.compile(r"gh[opusr]_[A-Za-z0-9]{30,}"),
    re.compile(r"glpat-[A-Za-z0-9_-]{20,}"),
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"AIza[0-9A-Za-z_-]{35}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"npm_[A-Za-z0-9]{36}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)


def find_public_secret(text: str, secret_values: Iterable[str] = ()) -> str | None:
    for secret in secret_values:
        if len(secret) >= 8 and secret in text:
            return "an exact protected secret value"
    for pattern in PUBLIC_SECRET_PATTERNS:
        if pattern.search(text):
            return f"a credential-shaped value ({pattern.pattern})"
    return None


def assert_public_text_has_no_secret(text: str) -> None:
    protected = [os.environ.get("HF_TOKEN", "")]
    finding = find_public_secret(text, protected)
    if finding:
        raise ValueError(f"public candidate contains {finding}")
