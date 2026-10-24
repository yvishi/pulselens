"""eval/load.py: reading labelled, analysed session bundles from a data directory."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from eval.freeze import frozen_ok, write_frozen
from eval.freeze import main as freeze_main
from eval.load import EvalSession, load_sessions
from eval.report import DISCLAIMER, render
from eval.report import main as report_main
from eval.run import main as run_main
from eval.run import metrics, refuse, wilson
from eval.separation import SeparationRow, auc, separation
from eval.separation import main as separation_main
from pulselens.bundle import write_bundle
from pulselens.contracts import CheckResult, Decision, FamilySummary, Label, Plan
from pulselens.engine.fusion import fuse
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


def test_wilson_interval() -> None:
    assert wilson(0, 10)[0] == 0.0
    assert wilson(0, 10)[1] == pytest.approx(0.278, abs=1e-3)
    assert wilson(5, 10) == pytest.approx((0.237, 0.763), abs=1e-3)
    assert wilson(10, 10)[1] == pytest.approx(1.0)
    assert wilson(0, 0) == (0.0, 1.0)


def test_write_frozen(tmp_path: Path) -> None:
    (tmp_path / "config.yaml").write_bytes(b"a: 1")
    path = write_frozen(["sensor.prnu"], root=tmp_path)
    assert path == tmp_path / "eval" / "FROZEN"
    data = json.loads(path.read_text())
    assert data["files"]["config.yaml"] == hashlib.sha256(b"a: 1").hexdigest()
    assert data["files"]["server/pulselens/analysis/thresholds.yaml"] == "missing"
    assert data["files"]["server/pulselens/analysis/thresholds.calibrated.yaml"] == "missing"
    assert data["voting_off"] == ["sensor.prnu"]


def test_freeze_detects_change(tmp_path: Path) -> None:
    assert frozen_ok(tmp_path) is False
    (tmp_path / "config.yaml").write_text("a: 1")
    write_frozen([], root=tmp_path)
    assert frozen_ok(tmp_path) is True
    (tmp_path / "config.yaml").write_text("a: 2")
    assert frozen_ok(tmp_path) is False
    (tmp_path / "eval" / "FROZEN").write_text("{not json")
    assert frozen_ok(tmp_path) is False


def vote_session() -> EvalSession:
    results = [usable("sensor.flag", "72% of frames repeated.", risk=0.9, flag=True),
               usable("light.ok", "Light matched.", family="C", vote_group="C.light"),
               usable("visual.ok", "Motion looked live.", family="D", vote_group="D.motion")]
    return EvalSession(session_id="v1", label=Label(**label()), mode=None, results=results, decision=None,
                       completed_at_ms=None)


def test_refuse_matches_fuse() -> None:
    s = vote_session()
    assert refuse(s, set()).outcome == fuse(s.results, None, 1, decided_at_ms=0).outcome == "RETRY_STEP_UP"


def test_voting_off_drops_vote() -> None:
    s = vote_session()
    on, off = refuse(s, set()), refuse(s, {"sensor.flag"})
    assert off.outcome != on.outcome
    assert "72% of frames repeated." not in " ".join(off.reasons)
    assert all(r != "72% of frames repeated." for r in off.reasons)


def _fam(family: str, flag: bool = False) -> CheckResult:
    return usable(f"t.{family.lower()}", f"{family} says so.", risk=0.9 if flag else 0.1, flag=flag, family=family,
                  vote_group=f"{family}.x")


PASS_RESULTS = [_fam("B"), _fam("C"), _fam("D")]
RETRY_RESULTS = [_fam("B", flag=True), _fam("C"), _fam("D")]
REVIEW_RESULTS = [_fam("B", flag=True), _fam("C", flag=True), _fam("D")]


def eval_session(sid: str, kind: str, results: list[CheckResult], decided_at_ms: int | None = None,
                 completed_at_ms: int | None = None) -> EvalSession:
    lab = Label.model_validate({**label(), "kind": kind})
    d = decision().model_copy(update={"decided_at_ms": decided_at_ms}) if decided_at_ms is not None else None
    return EvalSession(session_id=sid, label=lab, mode=None, results=results, decision=d,
                       completed_at_ms=completed_at_ms)


def test_apcer_bpcer_on_synthetic() -> None:
    sessions = [
        eval_session("g1", "genuine", PASS_RESULTS),
        eval_session("g2", "genuine", RETRY_RESULTS),
        eval_session("g3", "genuine", REVIEW_RESULTS),
        eval_session("a1", "live_swap", PASS_RESULTS),
        eval_session("a2", "live_swap", REVIEW_RESULTS),
    ]
    m = metrics(sessions, set())
    assert m.apcer == {"live_swap": (1, 2)}
    assert m.bpcer == (1, 3)
    assert m.retry == (1, 3)
    assert set(m.abstain) == {"A", "B", "C", "D"}
    assert all(n == 5 for _, n in m.abstain.values())
    assert m.abstain["A"] == (0, 5)
    assert m.latency_ms is None


def test_latency_median_p95() -> None:
    sessions = [eval_session(f"s{i}", "genuine", PASS_RESULTS, decided_at_ms=ms, completed_at_ms=0)
                for i, ms in enumerate([100, 200, 300, 400])]
    assert metrics(sessions, set()).latency_ms == (250.0, 400.0)
    assert metrics([eval_session("n", "genuine", PASS_RESULTS)], set()).latency_ms is None


def test_set_b_refused_without_freeze(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert run_main(["--set", "B", "--data", str(tmp_path)]) == 2
    assert "python -m eval.freeze first" in capsys.readouterr().err


def test_run_set_a_prints_x_of_n(tmp_path: Path, capsys) -> None:
    session(tmp_path, "g1", label())
    session(tmp_path, "g2", label())
    session(tmp_path, "a1", {**label(), "kind": "live_swap"})
    assert run_main(["--set", "A", "--data", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "set A, tuning set" in out
    assert "BPCER: " in out and " of 2 [" in out
    assert "APCER live_swap: " in out
    assert "device D01" in out
    assert "latency n/a" in out


def test_run_no_sessions(tmp_path: Path, capsys) -> None:
    assert run_main(["--set", "A", "--data", str(tmp_path)]) == 0
    assert "no labelled set A sessions with results" in capsys.readouterr().out


def test_freeze_main_writes_and_unlocks(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.yaml").write_text("a: 1")
    assert freeze_main(["--voting-off", "sensor.prnu, turn.identity"]) == 0
    assert frozen_ok(tmp_path) is True
    data = json.loads((tmp_path / "eval" / "FROZEN").read_text())
    assert data["voting_off"] == ["sensor.prnu", "turn.identity"]
    assert capsys.readouterr().out.startswith("wrote ")


def test_report_has_disclaimer_and_x_of_n() -> None:
    m = metrics([eval_session("a1", "live_swap", PASS_RESULTS), eval_session("a2", "live_swap", REVIEW_RESULTS)],
                set())
    text = render(None, m)
    assert DISCLAIMER in text
    assert "Set B not run" in text
    assert "## Tuning set (A)" in text
    assert "1 of 2 [" in text


def test_report_main_writes_file(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert report_main(["--data", str(tmp_path / "d"), "--out", str(tmp_path / "out")]) == 0
    text = (tmp_path / "out" / "report.md").read_text(encoding="utf-8")
    assert "No set A sessions." in text and "Set B not run" in text
    assert "report.md" in capsys.readouterr().out
