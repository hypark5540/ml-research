from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import sys
from copy import deepcopy
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from scripts.receive_codex_candidate import (
    MAX_CANDIDATE_BYTES,
    CandidateRejected,
    read_bounded,
    receive_candidate,
    require_production_approval,
    strict_json,
)
from tests.test_models import sample_digest

PUBLIC_SHA = "ab" * 20
TODAY = date(2026, 9, 6)
ROOT = Path(__file__).resolve().parents[1]


def candidate_bytes(week: str = "2026-09-06") -> bytes:
    payload = sample_digest()
    payload.update(
        weekOf=week,
        id=f"research-{week}",
        slug=f"weekly-ml-research-digest-{week}",
    )
    return (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode()


def event_for(raw: bytes, week: str = "2026-09-06") -> dict:
    return {
        "inputs": {
            "week_of": week,
            "candidate_b64": base64.b64encode(raw).decode("ascii"),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "expected_public_sha": PUBLIC_SHA,
        }
    }


def receive(event: dict) -> tuple[bytes, str, str]:
    return receive_candidate(event, public_sha=PUBLIC_SHA, today=TODAY)


def test_receive_preserves_exact_bytes_and_hash() -> None:
    raw = candidate_bytes()
    assert receive(event_for(raw)) == (
        raw,
        "2026-09-06",
        hashlib.sha256(raw).hexdigest(),
    )


def test_receive_leaves_canonical_byte_decision_to_production() -> None:
    raw = json.dumps(json.loads(candidate_bytes()), ensure_ascii=True).encode()
    assert receive(event_for(raw))[0] == raw


@pytest.mark.parametrize("week", ["2026-08-23", "2026-09-06"])
def test_receive_accepts_inclusive_seoul_date_boundaries(week: str) -> None:
    assert receive(event_for(candidate_bytes(week), week))[1] == week


@pytest.mark.parametrize(
    "week", ["2026-08-22", "2026-09-07", "2026-02-30", "20260906", " 2026-09-06"]
)
def test_receive_rejects_invalid_or_out_of_window_dates(week: str) -> None:
    event = event_for(candidate_bytes())
    event["inputs"]["week_of"] = week
    with pytest.raises(CandidateRejected, match="week"):
        receive(event)


@pytest.mark.parametrize(
    "field", ["week_of", "candidate_b64", "sha256", "expected_public_sha"]
)
def test_all_dispatch_inputs_are_required_strings(field: str) -> None:
    event = event_for(candidate_bytes())
    del event["inputs"][field]
    with pytest.raises(CandidateRejected, match="invalid_input_keys"):
        receive(event)
    event["inputs"][field] = 1
    with pytest.raises(CandidateRejected, match="invalid_input_type"):
        receive(event)


@pytest.mark.parametrize("event", [None, [], {}, {"inputs": []}])
def test_receive_rejects_invalid_event_shapes(event) -> None:
    with pytest.raises(CandidateRejected):
        receive(event)


def test_receive_rejects_unknown_input() -> None:
    event = event_for(candidate_bytes())
    event["inputs"]["output_path"] = "unexpected"
    with pytest.raises(CandidateRejected, match="invalid_input_keys"):
        receive(event)


@pytest.mark.parametrize("sha", ["cd" * 20, "main", "AB" * 20, "ab" * 20 + "\n"])
def test_receive_requires_exact_public_workflow_sha(sha: str) -> None:
    event = event_for(candidate_bytes())
    event["inputs"]["expected_public_sha"] = sha
    with pytest.raises(CandidateRejected, match="public_sha_mismatch"):
        receive(event)


def test_receive_rejects_malformed_runtime_sha() -> None:
    with pytest.raises(CandidateRejected, match="public_sha_mismatch"):
        receive_candidate(event_for(candidate_bytes()), public_sha="main", today=TODAY)


@pytest.mark.parametrize("sha", ["0" * 64, "F" * 64, "0" * 63, "0" * 64 + "\n"])
def test_receive_rejects_wrong_or_noncanonical_digest_sha(sha: str) -> None:
    event = event_for(candidate_bytes())
    event["inputs"]["sha256"] = sha
    with pytest.raises(CandidateRejected, match="sha"):
        receive(event)


@pytest.mark.parametrize(
    "encoded", ["e30=\n", "e3 0=", "e30===", "e30", "e_0=", "é", "e31="]
)
def test_receive_requires_strict_canonical_base64(encoded: str) -> None:
    event = event_for(b"{}")
    event["inputs"]["candidate_b64"] = encoded
    with pytest.raises(CandidateRejected, match="base64"):
        receive(event)


def test_receive_enforces_raw_transport_size_boundary() -> None:
    raw = candidate_bytes()
    # Whitespace is valid JSON; production still independently requires canonical
    # serialization. This exercises the intake byte limit without large fixtures.
    boundary = raw + b" " * (MAX_CANDIDATE_BYTES - len(raw))
    assert len(receive(event_for(boundary))[0]) == MAX_CANDIDATE_BYTES
    with pytest.raises(CandidateRejected, match="candidate_too_large"):
        receive(event_for(boundary + b" "))


@pytest.mark.parametrize("raw", [b"", b"0"])
def test_receive_rejects_empty_or_too_small_candidates(raw: bytes) -> None:
    with pytest.raises(CandidateRejected, match="invalid_candidate_size"):
        receive(event_for(raw))


def test_receive_enforces_entire_input_envelope_limit() -> None:
    event = event_for(candidate_bytes())
    event["inputs"]["candidate_b64"] = "A" * 65_535
    with pytest.raises(CandidateRejected, match="input_envelope_too_large"):
        receive(event)


@pytest.mark.parametrize(
    "raw",
    [
        b'{"value":"\xff"}',
        b"\xef\xbb\xbf{}",
        b'{"secret-looking-key":1,"secret-looking-key":2}',
        b'{"nested":{"value":1,"value":2}}',
        b'{"value":NaN}',
        b'{"value":Infinity}',
        b'{"value":-Infinity}',
    ],
)
def test_receive_rejects_invalid_utf8_duplicate_keys_and_non_json_numbers(
    raw: bytes,
) -> None:
    with pytest.raises(CandidateRejected):
        receive(event_for(raw))


def test_duplicate_key_error_never_reflects_key() -> None:
    with pytest.raises(CandidateRejected) as caught:
        strict_json(b'{"sensitive-marker":1,"sensitive-marker":2}')
    assert str(caught.value) == "duplicate_json_key"


def test_receive_rejects_candidate_week_mismatch() -> None:
    with pytest.raises(CandidateRejected, match="candidate_week_mismatch"):
        receive(event_for(candidate_bytes("2026-08-30")))


@pytest.mark.parametrize("kind", ["schema", "credential", "raw_auth"])
def test_receive_rejects_nonpublic_candidates_generically(kind: str) -> None:
    payload = json.loads(candidate_bytes())
    if kind == "schema":
        payload["papers"][0]["summaryEn"] = "sensitive-marker"
    elif kind == "credential":
        payload["papers"][0]["summaryEn"] += " hf_" + "a" * 30
    else:
        payload = {
            "weekOf": "2026-09-06",
            "auth_mode": "chatgpt",
            "tokens": {"access_token": "sensitive-marker"},
        }
    with pytest.raises(CandidateRejected) as caught:
        receive(event_for(json.dumps(payload).encode()))
    assert str(caught.value) == "invalid_candidate"


def production_response() -> dict:
    return {
        "valid": True,
        "validatorVersion": 1,
        "weekOf": "2026-09-06",
        "sha256": "a" * 64,
        "disposition": "new",
    }


@pytest.mark.parametrize("disposition", ["new", "already-published"])
def test_accepts_exact_production_approval(disposition: str) -> None:
    response = production_response()
    response["disposition"] = disposition
    require_production_approval(
        response, status="200", week_of="2026-09-06", sha256="a" * 64
    )


@pytest.mark.parametrize(
    "change",
    [
        {"valid": False},
        {"valid": "true"},
        {"valid": 1},
        {"sha256": "b" * 64},
        {"weekOf": "2026-08-30"},
        {"validatorVersion": 2},
        {"validatorVersion": True},
        {"disposition": "unknown"},
    ],
)
def test_rejects_inexact_production_approval(change: dict) -> None:
    response = production_response() | change
    with pytest.raises(CandidateRejected, match="production_validation_rejected"):
        require_production_approval(
            response, status="200", week_of="2026-09-06", sha256="a" * 64
        )


@pytest.mark.parametrize("status", ["400", "409", "422", "500", "302"])
def test_http_failure_cannot_approve_candidate(status: str) -> None:
    with pytest.raises(CandidateRejected, match="production_validation_rejected"):
        require_production_approval(
            production_response(), status=status, week_of="2026-09-06", sha256="a" * 64
        )


def cli_environment(tmp_path: Path) -> dict:
    return os.environ | {
        "GITHUB_REPOSITORY": "hypark5540/ml-research",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_SHA": PUBLIC_SHA,
        "GITHUB_OUTPUT": str(tmp_path / "github-output"),
    }


def run_receive_cli(
    tmp_path: Path, event: dict, environment: dict
) -> subprocess.CompletedProcess:
    event_file = tmp_path / "event.json"
    event_file.write_text(json.dumps(event), encoding="utf-8")
    return subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/receive_codex_candidate.py"),
            "receive",
            "--event-file",
            str(event_file),
            "--output",
            str(tmp_path / "generated/weekly-digest.json"),
        ],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_cli_writes_original_bytes_checksum_and_only_safe_outputs(
    tmp_path: Path,
) -> None:
    week = datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat()
    raw = candidate_bytes(week)
    result = run_receive_cli(tmp_path, event_for(raw, week), cli_environment(tmp_path))
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "generated/weekly-digest.json").read_bytes() == raw
    sha = hashlib.sha256(raw).hexdigest()
    assert (tmp_path / "generated/weekly-digest.sha256").read_text() == (
        f"{sha}  weekly-digest.json\n"
    )
    assert (tmp_path / "github-output").read_text() == f"week_of={week}\nsha256={sha}\n"
    assert json.loads(raw)["titleEn"] not in result.stdout + result.stderr


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("GITHUB_REPOSITORY", "other/ml-research"),
        ("GITHUB_REF", "refs/heads/feature"),
        ("GITHUB_EVENT_NAME", "pull_request"),
    ],
)
def test_cli_rejects_untrusted_execution_context(
    tmp_path: Path, key: str, value: str
) -> None:
    env = cli_environment(tmp_path) | {key: value}
    result = run_receive_cli(tmp_path, event_for(candidate_bytes()), env)
    assert result.returncode == 1
    assert "untrusted_workflow_context" in result.stderr
    assert not (tmp_path / "generated").exists()


def test_cli_schema_failure_contains_no_candidate_or_traceback(tmp_path: Path) -> None:
    week = datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat()
    payload = json.loads(candidate_bytes(week))
    payload["papers"][0]["summaryEn"] = "private-sensitive-marker"
    raw = json.dumps(payload).encode()
    result = run_receive_cli(tmp_path, event_for(raw, week), cli_environment(tmp_path))
    assert result.returncode == 1
    assert result.stderr == "Codex candidate rejected: invalid_candidate.\n"
    assert result.stdout == ""
    assert not (tmp_path / "generated").exists()


def test_response_cli_never_logs_rejection_body(tmp_path: Path) -> None:
    response_file = tmp_path / "response.json"
    response_file.write_text('{"valid":false,"error":"private-sensitive-marker"}')
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/receive_codex_candidate.py"),
            "check-response",
            "--response-file",
            str(response_file),
            "--status",
            "422",
            "--week-of",
            "2026-09-06",
            "--sha256",
            "a" * 64,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert (
        result.stderr == "Codex candidate rejected: production_validation_rejected.\n"
    )
    assert result.stdout == ""


def test_file_read_is_bounded(tmp_path: Path) -> None:
    path = tmp_path / "large.json"
    path.write_bytes(b"a" * 11)
    with pytest.raises(CandidateRejected, match="input_file_too_large"):
        read_bounded(path, 10)


def test_new_workflow_preserves_existing_immutable_publisher() -> None:
    old = (ROOT / ".github/workflows/weekly-digest.yml").read_text()
    new = (ROOT / ".github/workflows/publish-codex-digest.yml").read_text()
    expected = old.split("  publish:\n", 1)[1]
    expected = expected.replace("needs: [context, validate]", "needs: validate")
    expected = expected.replace(
        "verified-research-candidate", "verified-codex-candidate"
    )
    expected = expected.replace(
        "needs.context.outputs.week_of", "needs.validate.outputs.week_of"
    )
    publisher = new.split("  publish:\n", 1)[1].split("\n  alert:\n", 1)[0]
    assert publisher.rstrip() == expected.rstrip()


def test_failure_alert_has_only_issue_permission_and_trusted_failure_guard() -> None:
    workflow = (ROOT / ".github/workflows/publish-codex-digest.yml").read_text()
    alert = workflow.split("\n  alert:\n", 1)[1]
    assert "needs: [validate, publish]" in alert
    assert "always() && github.repository == 'hypark5540/ml-research'" in alert
    assert "github.ref == 'refs/heads/main'" in alert
    assert "github.event_name == 'workflow_dispatch'" in alert
    assert "needs.validate.result == 'failure'" in alert
    assert "needs.publish.result == 'failure'" in alert
    permissions = alert.split("    permissions:\n", 1)[1].split("    steps:\n", 1)[0]
    assert permissions.strip() == "issues: write"
    assert "uses:" not in alert
    assert "secrets." not in alert


def test_failure_alert_command_contains_only_generic_text_and_run_link() -> None:
    workflow = (ROOT / ".github/workflows/publish-codex-digest.yml").read_text()
    alert = workflow.split("\n  alert:\n", 1)[1]
    command = " ".join(alert.split("        run: >-\n", 1)[1].splitlines())
    environment = {
        "GITHUB_REPOSITORY": "hypark5540/ml-research",
        "GITHUB_RUN_ID": "123456789",
        "GH_TOKEN": "not-exposed-by-the-alert",
        "CANDIDATE_B64": "candidate-must-not-be-logged",
    }
    # Capture the generated CLI arguments without invoking gh or a remote system.
    stub = 'gh() { printf "%s\\n" "$@"; }; '
    result = subprocess.run(
        ["bash", "-c", stub + command],
        env=environment,
        text=True,
        capture_output=True,
        check=True,
    )
    args = result.stdout.splitlines()
    assert args[:2] == ["issue", "create"]
    assert args[args.index("--assignee") + 1] == "hypark5540"
    assert args[args.index("--body") + 1] == (
        "Public research validation or publication workflow failed. "
        "Inspect the run at "
        "https://github.com/hypark5540/ml-research/actions/runs/123456789."
    )
    assert "candidate-must-not-be-logged" not in result.stdout
    assert "not-exposed-by-the-alert" not in result.stdout


def test_empty_or_wrong_type_production_response_is_rejected() -> None:
    for response in ({}, None, [], deepcopy(production_response()) | {"sha256": None}):
        with pytest.raises(CandidateRejected):
            require_production_approval(
                response, status="200", week_of="2026-09-06", sha256="a" * 64
            )
