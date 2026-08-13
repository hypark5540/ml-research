from __future__ import annotations

import json
import subprocess
import sys


def test_render_prompt_reserves_iterations_for_a_validated_file(tmp_path) -> None:
    topics = tmp_path / "topics.json"
    archive = tmp_path / "archive.json"
    output = tmp_path / "digest.json"
    topics.write_text(json.dumps({"tracks": []}), encoding="utf-8")
    archive.write_text(json.dumps({"version": 1, "digests": []}), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/render_prompt.py",
            "--topics",
            str(topics),
            "--archive",
            str(archive),
            "--output",
            str(output),
            "--week-of",
            "2026-08-09",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Stop expanding the candidate pool" in result.stdout
    assert "at most 35 tool-call iterations" in result.stdout
    assert "Reserve at least 15 iterations" in result.stdout
    assert "A text-only research summary is not a completed task" in result.stdout
