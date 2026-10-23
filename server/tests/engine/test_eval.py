"""eval/load.py: reading labelled, analysed session bundles from a data directory."""

from __future__ import annotations

import json
from pathlib import Path

from eval.load import EvalSession, load_sessions
from eval.separation import SeparationRow, auc, separation
from eval.separation import main as separation_main
from pulselens.bundle import write_bundle
from pulselens.contracts import CheckResult, Decision, FamilySummary, Label, Plan
from pulselens.engine.results import abstain, usable


def label(set_: str = "A") -> dict:
    return {"person": "P01", "device": "D01", "light": "normal", "kind": "genuine", "set": set_, "consent_ref": "c1"}


def session(root: Path, sid: str, lab: dict | None, *, results: bool = True, plan: Plan | None = None,
            decision: Decision | None = None, completed_at_ms: int | None = None) -> Path:
    path = root / sid
    meta: dict = {"session_id": sid, "label": lab}
    if completed_at_ms is not None:
        meta["completed_at_ms"] = completed_at_ms
    write_bundle(path, session=meta, preflight=None, plan=plan, challenge=None, frames=[], events=[])
    if results:
        rows = [usable("integrity.order", "ok").model_dump(mode="json"),
                abstain("stream.fps", "too few frames", ["FPS_LOW"]).model_dump(mode="json")]
        (path / "results.json").write_text(json.dumps(rows), encoding="utf-8")
    if decision is not None:
        (path / "decision.json").write_text(decision.model_dump_json(), encoding="utf-8")
    return path


def decision() -> Decision:
    fams = [FamilySummary(family=f, state="not_run", usable_checks=0, flagged_checks=0, reasons=[])
            for f in ("A", "B", "C", "D")]
    return Decision(outcome="HUMAN_REVIEW", step_up="agent_checks", families=fams, reasons=["r"],
                    integrity_violation=False, provisional=True, decided_at_ms=5)


def test_load_skips_unlabelled_and_unanalysed(tmp_path: Path) -> None:
    session(tmp_path, "a1", label())
    session(tmp_path, "b2", None)
    session(tmp_path, "c3", label(), results=False)
    out = load_sessions(tmp_path)
    assert [s.session_id for s in out] == ["a1"]
    assert out[0].label.person == "P01"
    assert [r.check_id for r in out[0].results] == ["integrity.order", "stream.fps"]
    assert out[0].decision is None and out[0].mode is None and out[0].completed_at_ms is None


def test_load_filters_set(tmp_path: Path) -> None:
    session(tmp_path, "s2", label("B"))
    session(tmp_path, "s1", label("A"))
    assert [s.session_id for s in load_sessions(tmp_path, "A")] == ["s1"]
    assert [s.session_id for s in load_sessions(tmp_path, "B")] == ["s2"]
    assert [s.session_id for s in load_sessions(tmp_path)] == ["s1", "s2"]


def test_load_reads_decision_and_mode(tmp_path: Path) -> None:
    plan = Plan(mode="CAPABLE", run_light=True, run_turn=True, agent_questions=False, reasons=[])
    session(tmp_path, "d1", label(), plan=plan, decision=decision(), completed_at_ms=123)
    (s,) = load_sessions(tmp_path)
    assert s.decision is not None and s.decision.outcome == "HUMAN_REVIEW"
    assert s.mode == "CAPABLE"
    assert s.completed_at_ms == 123


def test_load_skips_invalid_json(tmp_path: Path) -> None:
    session(tmp_path, "ok", label())
    bad = session(tmp_path, "bad1", label())
    (bad / "results.json").write_text('[{"check_id": 1}]', encoding="utf-8")
    bad2 = session(tmp_path, "bad2", label())
    (bad2 / "results.json").write_text("not json", encoding="utf-8")
    bad3 = session(tmp_path, "bad3", label(), decision=decision())
    (bad3 / "decision.json").write_text("{}", encoding="utf-8")
    assert [s.session_id for s in load_sessions(tmp_path)] == ["ok"]


def test_load_missing_dir_and_stray_files(tmp_path: Path) -> None:
    assert load_sessions(tmp_path / "nope") == []
    (tmp_path / "note.txt").write_text("x", encoding="utf-8")
    assert load_sessions(tmp_path) == []


def test_auc_perfect_inverse_and_ties() -> None:
    assert auc([0.1, 0.2], [0.8, 0.9]) == 1.0
    assert auc([0.8, 0.9], [0.1, 0.2]) == 0.0
    assert auc([0.5], [0.5]) == 0.5
    assert auc([], [1.0]) is None
    assert auc([1.0], []) is None


def sep_session(sid: str, kind: str, results: list[CheckResult]) -> EvalSession:
    lab = Label.model_validate({**label(), "kind": kind})
    return EvalSession(session_id=sid, label=lab, mode=None, results=results, decision=None, completed_at_ms=None)


def test_separation_usable_only() -> None:
    cid = "light.response"
    sessions = [
        sep_session("g1", "genuine", [usable(cid, "x", risk=0.1)]),
        sep_session("g2", "genuine", [usable(cid, "x", risk=0.2)]),
        sep_session("g3", "genuine", [abstain(cid, "x", ["LOW"])]),
        sep_session("a1", "live_swap", [usable(cid, "x", risk=0.8)]),
        sep_session("a2", "live_swap", [usable(cid, "x", risk=0.9)]),
    ]
    assert separation(sessions) == [SeparationRow(cid, "live_swap", 1.0, 2, 2)]


def test_separation_max_risk_per_session() -> None:
    cid = "light.response"
    sessions = [
        sep_session("g1", "genuine", [usable(cid, "x", risk=0.5)]),
        sep_session("a1", "live_swap", [usable(cid, "x", risk=0.1), usable(cid, "x", risk=0.9)]),
    ]
    assert separation(sessions) == [SeparationRow(cid, "live_swap", 1.0, 1, 1)]
    sessions[1] = sep_session("a1", "live_swap", [usable(cid, "x", risk=0.1), usable(cid, "x", risk=0.4)])
    assert separation(sessions)[0].auc == 0.0


def test_separation_missing_side_is_none() -> None:
    cid = "light.response"
    sessions = [sep_session("a1", "replay_screen", [usable(cid, "x", risk=0.7)])]
    assert separation(sessions) == [SeparationRow(cid, "replay_screen", None, 0, 1)]


def _write_light_sessions(root: Path, set_: str) -> None:
    specs = [("g1", "genuine", 0.1), ("g2", "genuine", 0.2), ("a1", "live_swap", 0.8), ("a2", "live_swap", 0.9)]
    for sid, kind, risk in specs:
        path = session(root, sid, {**label(set_), "kind": kind})
        rows = [usable("light.response", "x", risk=risk).model_dump(mode="json")]
        (path / "results.json").write_text(json.dumps(rows), encoding="utf-8")


def test_separation_main_prints_and_writes_csv(tmp_path: Path, capsys) -> None:
    data, out = tmp_path / "data", tmp_path / "out"
    _write_light_sessions(data, "A")
    assert separation_main(["--data", str(data), "--out", str(out)]) == 0
    assert "light.response vs live_swap: AUC 1.00 (genuine n=2, live_swap n=2)" in capsys.readouterr().out
    lines = (out / "separation.csv").read_text(encoding="utf-8").splitlines()
    assert lines[0] == "check_id,kind,auc,n_genuine,n_attack"
    assert lines[1] == "light.response,live_swap,1.0,2,2"


def test_separation_main_ignores_set_b(tmp_path: Path, capsys) -> None:
    data, out = tmp_path / "data", tmp_path / "out"
    _write_light_sessions(data, "B")
    assert separation_main(["--data", str(data), "--out", str(out)]) == 0
    assert "no labelled set A sessions with results" in capsys.readouterr().out
