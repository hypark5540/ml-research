import hashlib
from datetime import date
from pathlib import Path

import pytest

from scripts.receive_codex_candidate import CandidateRejected, receive_candidate
from tests.test_receive_codex_candidate import PUBLIC_SHA, event_for


def test_finance_intake_preserves_bytes_and_series_is_explicit():
    raw = (Path(__file__).parent / "fixtures/finance-digest.json").read_bytes()
    event = event_for(raw, "2026-09-13")
    assert receive_candidate(
        event, public_sha=PUBLIC_SHA, today=date(2026, 9, 13), series="finance"
    ) == (raw, "2026-09-13", hashlib.sha256(raw).hexdigest())
    with pytest.raises(CandidateRejected):
        receive_candidate(event, public_sha=PUBLIC_SHA, today=date(2026, 9, 13))
    with pytest.raises(CandidateRejected):
        receive_candidate(
            event, public_sha=PUBLIC_SHA, today=date(2026, 9, 13), series="unknown"
        )
