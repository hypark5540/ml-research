#!/usr/bin/env python3
"""Receive public digest bytes without evaluating or reserializing dispatch input."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from ml_research.models import WeeklyDigest
from ml_research.finance_models import Digest as FinanceDigest
from ml_research.public_scan import assert_public_text_has_no_secret

MAX_CANDIDATE_BYTES = 45 * 1024
MAX_INPUT_CHARACTERS = 65_535
MAX_EVENT_BYTES = 1024 * 1024
INPUT_KEYS = frozenset({"week_of", "candidate_b64", "sha256", "expected_public_sha"})
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
COMMIT_RE = re.compile(r"[0-9a-f]{40}\Z")
DATE_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")


class CandidateRejected(ValueError):
    """An error code that never contains untrusted candidate data."""


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise CandidateRejected("duplicate_json_key")
        value[key] = item
    return value


def reject_constant(value: str) -> None:
    del value
    raise CandidateRejected("invalid_json")


def strict_json(raw: bytes) -> Any:
    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=unique_object,
            parse_constant=reject_constant,
        )
    except CandidateRejected:
        raise
    except (UnicodeError, ValueError, RecursionError) as error:
        raise CandidateRejected("invalid_json_or_utf8") from error


def receive_candidate(
    event: Any, *, public_sha: str, today: date, series: str = "research"
) -> tuple[bytes, str, str]:
    """Validate the dispatch envelope and Python policy, retaining original bytes.

    The production API remains authoritative for its stricter schema and canonical
    JSON rules; a Python pass must never be interpreted as publication approval.
    """
    if not isinstance(event, dict):
        raise CandidateRejected("invalid_event")
    inputs = event.get("inputs")
    if not isinstance(inputs, dict) or set(inputs) != INPUT_KEYS:
        raise CandidateRejected("invalid_input_keys")
    if any(not isinstance(value, str) for value in inputs.values()):
        raise CandidateRejected("invalid_input_type")
    envelope = json.dumps(inputs, ensure_ascii=True, separators=(",", ":"))
    if len(envelope) > MAX_INPUT_CHARACTERS:
        raise CandidateRejected("input_envelope_too_large")

    expected_sha = inputs["sha256"]
    expected_public_sha = inputs["expected_public_sha"]
    if not SHA256_RE.fullmatch(expected_sha):
        raise CandidateRejected("invalid_sha256")
    if (
        not COMMIT_RE.fullmatch(public_sha)
        or not COMMIT_RE.fullmatch(expected_public_sha)
        or expected_public_sha != public_sha
    ):
        raise CandidateRejected("public_sha_mismatch")

    week_of = inputs["week_of"]
    if not DATE_RE.fullmatch(week_of):
        raise CandidateRejected("invalid_week")
    try:
        week = date.fromisoformat(week_of)
    except ValueError as error:
        raise CandidateRejected("invalid_week") from error
    if not today - timedelta(days=14) <= week <= today:
        raise CandidateRejected("week_outside_window")

    encoded = inputs["candidate_b64"]
    if len(encoded) > 4 * ((MAX_CANDIDATE_BYTES + 2) // 3):
        raise CandidateRejected("candidate_too_large")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, UnicodeError) as error:
        raise CandidateRejected("invalid_base64") from error
    if base64.b64encode(raw).decode("ascii") != encoded:
        raise CandidateRejected("non_canonical_base64")
    if not 2 <= len(raw) <= MAX_CANDIDATE_BYTES:
        raise CandidateRejected("invalid_candidate_size")
    digest_sha = hashlib.sha256(raw).hexdigest()
    if digest_sha != expected_sha:
        raise CandidateRejected("candidate_sha_mismatch")

    payload = strict_json(raw)
    if not isinstance(payload, dict) or payload.get("weekOf") != week_of:
        raise CandidateRejected("candidate_week_mismatch")
    try:
        assert_public_text_has_no_secret(raw.decode("utf-8"))
        if series not in {"research", "finance"}:
            raise ValueError("unsupported_series")
        (FinanceDigest if series == "finance" else WeeklyDigest).model_validate(payload)
    except (ValueError, TypeError, RecursionError) as error:
        raise CandidateRejected("invalid_candidate") from error
    return raw, week_of, digest_sha


def require_production_approval(
    response: Any, *, status: str, week_of: str, sha256: str
) -> None:
    if (
        status != "200"
        or not isinstance(response, dict)
        or response.get("valid") is not True
        or type(response.get("validatorVersion")) is not int
        or response["validatorVersion"] != 1
        or response.get("weekOf") != week_of
        or response.get("sha256") != sha256
        or response.get("disposition") not in ("new", "already-published")
    ):
        raise CandidateRejected("production_validation_rejected")


def write_candidate(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(dir=path.parent, prefix=".candidate-")
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def read_bounded(path: Path, maximum: int) -> bytes:
    with path.open("rb") as handle:
        raw = handle.read(maximum + 1)
    if len(raw) > maximum:
        raise CandidateRejected("input_file_too_large")
    return raw


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    receive = commands.add_parser("receive")
    receive.add_argument("--event-file", type=Path, required=True)
    receive.add_argument("--output", type=Path, required=True)
    receive.add_argument(
        "--series", choices=["research", "finance"], default="research"
    )
    approval = commands.add_parser("check-response")
    approval.add_argument("--response-file", type=Path, required=True)
    approval.add_argument("--status", required=True)
    approval.add_argument("--week-of", required=True)
    approval.add_argument("--sha256", required=True)
    args = parser.parse_args()

    try:
        if args.command == "check-response":
            require_production_approval(
                strict_json(read_bounded(args.response_file, 65_536)),
                status=args.status,
                week_of=args.week_of,
                sha256=args.sha256,
            )
            print("Production validator approved the exact candidate.")
            return 0

        if (
            os.environ.get("GITHUB_REPOSITORY") != "hypark5540/ml-research"
            or os.environ.get("GITHUB_REF") != "refs/heads/main"
            or os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
        ):
            raise CandidateRejected("untrusted_workflow_context")
        raw, week_of, sha256 = receive_candidate(
            strict_json(read_bounded(args.event_file, MAX_EVENT_BYTES)),
            public_sha=os.environ.get("GITHUB_SHA", ""),
            today=datetime.now(ZoneInfo("Asia/Seoul")).date(),
            series=args.series,
        )
        write_candidate(args.output, raw)
        args.output.with_suffix(".sha256").write_text(
            f"{sha256}  {args.output.name}\n", encoding="ascii"
        )
        with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="ascii") as handle:
            handle.write(f"week_of={week_of}\nsha256={sha256}\n")
        print("Candidate passed local intake; production approval is still required.")
    except CandidateRejected as error:
        print(f"Codex candidate rejected: {error}.", file=sys.stderr)
        return 1
    except Exception:
        # Do not expose paths, JSON, Pydantic input values, or API response bodies.
        print("Codex candidate rejected: intake_unavailable.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
