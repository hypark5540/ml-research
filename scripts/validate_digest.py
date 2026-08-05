#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from pydantic import ValidationError

from ml_research.io import read_json
from ml_research.models import DigestArchive, WeeklyDigest


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a digest or digest archive")
    parser.add_argument("path", type=Path)
    parser.add_argument(
        "--archive",
        action="store_true",
        help="Require the versioned archive document shape",
    )
    args = parser.parse_args()

    try:
        payload = read_json(args.path)
        if args.archive or "digests" in payload:
            value = DigestArchive.model_validate(payload)
            summary = f"valid archive: {len(value.digests)} digest(s)"
        else:
            value = WeeklyDigest.model_validate(payload)
            summary = f"valid digest: {value.id} ({len(value.papers)} papers)"
    except (OSError, json.JSONDecodeError, ValidationError, TypeError) as error:
        print(f"validation failed: {error}")
        return 1

    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
