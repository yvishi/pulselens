"""SessionStore behaviours that must hold under repeated or concurrent calls."""

from __future__ import annotations

import json
from pathlib import Path

from pulselens.config import load_config
from pulselens.contracts import Plan, SessionCreate
from pulselens.engine import audit
from pulselens.engine.planner import make_challenge, rng_for_nonce
from pulselens.engine.store import SessionStore


def test_issue_challenge_is_single_use_and_audited(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "data")
    created = store.create(SessionCreate())
    sid, nonce = created.session_id, created.nonce
    plan = Plan(mode="CAPABLE", run_light=True, run_turn=True, agent_questions=False, reasons=[])
    challenge = make_challenge(plan, sid, nonce, rng_for_nonce(nonce), load_config())

    assert store.issue_challenge(sid, challenge) is True
    assert store.issue_challenge(sid, challenge) is False

    folder = store.path(sid)
    assert (folder / "challenge.json").exists()
    assert store.get(sid)["state"] == "capturing"
    types = [json.loads(line)["type"] for line in (folder / "audit.jsonl").read_text(encoding="utf-8").splitlines()]
    assert types == ["session.created", "challenge.issued"]
    assert audit.verify(folder) == (True, None)

