"""K4: the analysis runner and fake analysis."""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pulselens.api.main import create_app
from pulselens.bundle import write_bundle
from pulselens.config import Settings, load_config
from pulselens.contracts import ChallengeEvent, ColourStep, FrameMeta, Plan, SessionCreate
from pulselens.engine import fake_analysis
from pulselens.engine.runner import choose_analyze, run_analysis
from pulselens.engine.store import SessionStore
from tests.engine.api import SyncExecutor, drive

JPEG = b"\xff\xd8\xff\xd9"


def full_session(store: SessionStore, n: int = 120) -> Path:
    """A completed CAPABLE session written into the store: plan, challenge, n frames, every step shown."""
    created = store.create(SessionCreate())
    folder = store.path(created.session_id)
    plan = Plan(mode="CAPABLE", run_light=True, run_turn=True, agent_questions=False, reasons=["mode.capable.ok"])
    from pulselens.engine.planner import make_challenge, rng_for_nonce

    ch = make_challenge(plan, created.session_id, created.nonce, rng_for_nonce(created.nonce), load_config())
    events = [ChallengeEvent(step_id=s.step_id, status="shown", painted_t_ms=ch.baseline_ms + s.start_offset_ms + 5.0,
                             ended_t_ms=None, shown_rgb=(0.6, 0.5, 0.3) if isinstance(s, ColourStep) else None)
              for s in ch.steps]
    write_bundle(folder, session=store.get(created.session_id), preflight=None, plan=plan, challenge=ch,
                 frames=[(FrameMeta(idx=i, t_ms=i * 33.3, w=640, h=480), JPEG) for i in range(n)], events=events)
    store.set_state(created.session_id, "analysing")
    return folder


@pytest.fixture
def store(tmp_path: Path) -> SessionStore:
    return SessionStore(tmp_path / "data")


@pytest.fixture
def pool():
    with ThreadPoolExecutor(max_workers=2) as p:
        yield p


def test_runner_with_fake(store: SessionStore, pool) -> None:
    folder = full_session(store)
    decision = run_analysis(folder, store, pool=pool, fake=True)
    assert decision.outcome == "PASS" and decision.provisional
    assert (folder / "decision.json").exists() and store.get(folder.name)["state"] == "done"
    results = json.loads((folder / "results.json").read_text())
    ids = [r["check_id"] for r in results]
    assert ids == ["integrity.protocol", "integrity.coverage", "fake.b", "fake.c", "fake.d"]
    assert all(r["explanation"] == fake_analysis.EXPLANATION for r in results if r["check_id"].startswith("fake."))


def test_runner_stamps_the_store_clock(tmp_path: Path, pool) -> None:
    clock_store = SessionStore(tmp_path / "data", clock=lambda: 1_700_000_000_123.0)
    folder = full_session(clock_store)
    decision = run_analysis(folder, clock_store, pool=pool, fake=True)
    assert decision.decided_at_ms == 1_700_000_000_123


def test_runner_survives_analysis_exception(store: SessionStore, pool) -> None:
    folder = full_session(store)

    def boom(_: Path):
        raise RuntimeError("model file missing")

    decision = run_analysis(folder, store, pool=pool, analyze=boom)
    results = json.loads((folder / "results.json").read_text())
    error = next(r for r in results if r["check_id"] == "analysis.error")
    assert error["status"] == "abstain" and error["family"] == "B" and error["reason_codes"] == ["analysis.error"]
    assert store.get(folder.name)["state"] == "done"
    assert decision.outcome == "RETRY_STEP_UP"  # only integrity is usable: low coverage, never a fraud flag


def test_runner_timeout(store: SessionStore, pool) -> None:
    folder = full_session(store)

    def slow(_: Path):
        time.sleep(2)
        return fake_analysis.analyze(folder)

    t0 = time.monotonic()
    run_analysis(folder, store, pool=pool, analyze=slow, timeout_s=1)
    assert time.monotonic() - t0 < 1.8
    results = json.loads((folder / "results.json").read_text())
    assert [r["check_id"] for r in results][-1] == "analysis.error"
    assert "did not finish in 1 s" in results[-1]["explanation"]


def test_runner_rejects_a_bad_return_value(store: SessionStore, pool) -> None:
    folder = full_session(store)
    run_analysis(folder, store, pool=pool, analyze=lambda _: {"not": "a list"})
    assert json.loads((folder / "results.json").read_text())[-1]["check_id"] == "analysis.error"


def test_choose_analyze(monkeypatch: pytest.MonkeyPatch) -> None:
    assert choose_analyze(True) is fake_analysis.analyze
    import pulselens.analysis as analysis

    def real(_: Path):
        return []

    monkeypatch.setattr(analysis, "analyze", real, raising=False)
    assert choose_analyze(False) is real
    monkeypatch.delattr(analysis, "analyze")
    assert choose_analyze(False) is fake_analysis.analyze  # no analyze yet: the fake, clearly labelled


def test_complete_runs_the_runner_end_to_end(tmp_path: Path) -> None:
    settings = Settings(agent_passcode="pc", data_dir=tmp_path / "data", fake_analysis=True)
    with TestClient(create_app(settings, executor=SyncExecutor())) as client:
        s = drive(client)
        sid = s["session_id"]
        h = {"Authorization": f"Bearer {s['customer_token']}"}
        status = client.get(f"/api/sessions/{sid}/status", headers=h).json()
    assert status == {"state": "done", "message": "continue"}
    decision = json.loads((tmp_path / "data" / sid / "decision.json").read_text())
    assert decision["outcome"] == "PASS" and decision["provisional"]


def test_the_app_owns_and_closes_both_pools(tmp_path: Path) -> None:
    settings = Settings(agent_passcode="pc", data_dir=tmp_path / "data", fake_analysis=True)
    with TestClient(create_app(settings)) as client:
        pools = (client.app.state.executor, client.app.state.analyze_pool)
        assert client.app.state.runner.keywords["pool"] is pools[1]
    for p in pools:
        with pytest.raises(RuntimeError):
            p.submit(print)  # shut down with the app
