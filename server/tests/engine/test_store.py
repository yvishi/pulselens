"""SessionStore behaviours that must hold under repeated or concurrent calls."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pulselens.config import load_config
from pulselens.contracts import AgentDecision, Decision, FrameBatchMeta, FrameMeta, Label, Plan, SessionCreate
from pulselens.engine import audit
from pulselens.engine.fusion import fuse
from pulselens.engine.planner import make_challenge, rng_for_nonce
from pulselens.engine.results import usable
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


def test_save_analysis_writes_both_files_audits_and_finishes(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "data")
    sid = store.create(SessionCreate()).session_id
    results = [usable("B.one", "first check"), usable("B.two", "second check", risk=0.2)]
    decision = fuse(results, None, 1, decided_at_ms=0)

    store.save_analysis(sid, results, decision)

    folder = store.path(sid)
    results_bytes = (folder / "results.json").read_bytes()
    assert json.loads(results_bytes) == [r.model_dump(mode="json") for r in results]
    assert Decision.model_validate_json((folder / "decision.json").read_text(encoding="utf-8")) == decision
    rows = [json.loads(line) for line in (folder / "audit.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [r["type"] for r in rows][-2:] == ["analysis.done", "decision.made"]
    assert rows[-2]["payload_sha256"] == hashlib.sha256(results_bytes).hexdigest()
    assert store.get(sid)["state"] == "done"
    assert list(folder.glob("*.tmp")) == []
    assert audit.verify(folder) == (True, None)


def test_record_agent_saves_and_audits(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "data")
    sid = store.create(SessionCreate()).session_id

    store.record_agent(sid, AgentDecision(action="escalate", note="check ID"))

    folder = store.path(sid)
    assert json.loads((folder / "agent.json").read_text(encoding="utf-8")) == {"action": "escalate", "note": "check ID"}
    rows = [json.loads(line) for line in (folder / "audit.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows[-2]["type"] == "agent.action"
    assert rows[-1]["type"] == "frames.deleted"
    assert audit.verify(folder) == (True, None)
    assert list(folder.glob("*.tmp")) == []


def test_only_the_store_writes_audit_lines():
    root = Path(__file__).resolve().parents[2] / "pulselens"
    users = sorted(p.relative_to(root).as_posix() for p in root.rglob("*.py")
                   if "engine import audit" in p.read_text(encoding="utf-8") and p.name != "audit.py")
    assert users == ["engine/store.py"]


def test_record_agent_deletes_frames_for_customer_session(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "data", delete_frames_on_decision=True)
    sid = store.create(SessionCreate()).session_id
    meta = FrameBatchMeta(batch_seq=0, frames=[FrameMeta(idx=0, t_ms=0, w=100, h=100)])
    store.append_frames(sid, meta, [b"\xff\xd8\xff\xd9"])

    folder = store.path(sid)
    assert store.frame_count(sid) == 1
    assert (folder / "frames").exists()

    store.record_agent(sid, AgentDecision(action="approve"))

    assert not (folder / "frames").exists()
    assert store.frame_count(sid) == 1
    rows = [json.loads(line) for line in (folder / "audit.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows[-2]["type"] == "agent.action"
    assert rows[-1]["type"] == "frames.deleted"
    assert audit.verify(folder) == (True, None)


def test_record_agent_preserves_frames_for_lab_session(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "data", delete_frames_on_decision=True)
    label = Label(person="P01", device="D01", light="normal", kind="genuine", set="A", consent_ref="signed")
    sid = store.create(SessionCreate(label=label)).session_id
    meta = FrameBatchMeta(batch_seq=0, frames=[FrameMeta(idx=0, t_ms=0, w=100, h=100)])
    store.append_frames(sid, meta, [b"\xff\xd8\xff\xd9"])

    folder = store.path(sid)
    store.record_agent(sid, AgentDecision(action="approve"))

    assert (folder / "frames").exists()
    assert store.frame_count(sid) == 1
    rows = [json.loads(line) for line in (folder / "audit.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows[-1]["type"] == "agent.action"
    assert "frames.deleted" not in [r["type"] for r in rows]
    assert audit.verify(folder) == (True, None)


def test_record_agent_preserves_frames_when_disabled(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "data", delete_frames_on_decision=False)
    sid = store.create(SessionCreate()).session_id
    meta = FrameBatchMeta(batch_seq=0, frames=[FrameMeta(idx=0, t_ms=0, w=100, h=100)])
    store.append_frames(sid, meta, [b"\xff\xd8\xff\xd9"])

    folder = store.path(sid)
    store.record_agent(sid, AgentDecision(action="approve"))

    assert (folder / "frames").exists()
    assert store.frame_count(sid) == 1
    rows = [json.loads(line) for line in (folder / "audit.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows[-1]["type"] == "agent.action"
    assert "frames.deleted" not in [r["type"] for r in rows]

