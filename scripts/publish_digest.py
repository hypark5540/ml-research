#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from ml_research.io import atomic_write_json, read_json
from ml_research.models import DigestArchive, WeeklyDigest


def load_digest(path: Path) -> WeeklyDigest:
    payload = read_json(path)
    if set(payload) == {"digest"}:
        payload = payload["digest"]
    return WeeklyDigest.model_validate(payload)


def append_digest(digest: WeeklyDigest, target: Path) -> DigestArchive:
    if target.exists():
        archive = DigestArchive.model_validate(read_json(target))
    else:
        archive = DigestArchive(version=1, digests=[])

    if any(existing.id == digest.id for existing in archive.digests):
        raise ValueError(f"digest {digest.id} already exists")

    merged = DigestArchive(
        version=1,
        digests=sorted(
            [*archive.digests, digest], key=lambda value: value.weekOf, reverse=True
        ),
    )
    atomic_write_json(target, merged.model_dump(mode="json"))
    return merged


def main() -> int:
    parser = argparse.ArgumentParser(description="Append one validated weekly digest")
    parser.add_argument("--digest", required=True, type=Path)
    parser.add_argument("--target", required=True, type=Path)
    args = parser.parse_args()

    digest = load_digest(args.digest)
    archive = append_digest(digest, args.target)
    print(
        f"published {digest.id} with {len(digest.papers)} papers; "
        f"archive now has {len(archive.digests)} digest(s)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
