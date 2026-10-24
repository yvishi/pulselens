"""Purge sweep: demo purge by age, labelled purge after the event, and what it must never delete."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient

from pulselens.api.main import create_app
from pulselens.config import Settings
from pulselens.engine.purge import purge

NOW_MS = 10_000_000_000.0
MIN_MS = 60_000


def _session(data_dir: Path, sid: str, *, age_ms: float, label: dict | None = None, state: str = "done") -> Path:
    folder = data_dir / sid
    folder.mkdir()
    body = {"created_at_ms": int(NOW_MS - age_ms), "label": label, "state": state}
    (folder / "session.json").write_text(json.dumps(body), encoding="utf-8")
    return folder


def test_purge_keeps_labelled(tmp_path: Path) -> None:
    folder = _session(tmp_path, "aa", age_ms=120 * MIN_MS, label={"kind": "real"})
    assert purge(tmp_path, now_ms=NOW_MS) == []
    assert folder.exists()


def test_purge_removes_old_demo(tmp_path: Path) -> None:
    folder = _session(tmp_path, "bb", age_ms=61 * MIN_MS)
    assert purge(tmp_path, now_ms=NOW_MS) == ["bb"]
    assert not folder.exists()


def test_purge_keeps_recent_demo(tmp_path: Path) -> None:
    folder = _session(tmp_path, "cc", age_ms=59 * MIN_MS)
    assert purge(tmp_path, now_ms=NOW_MS) == []
    assert folder.exists()


def test_purge_skips_unreadable_and_analysing(tmp_path: Path) -> None:
    bad = tmp_path / "dd"
    bad.mkdir()
    (bad / "session.json").write_text("{not json", encoding="utf-8")
    missing = tmp_path / "ee"
    missing.mkdir()
    analysing = _session(tmp_path, "ff", age_ms=120 * MIN_MS, state="analysing")
    assert purge(tmp_path, now_ms=NOW_MS) == []
    assert purge(tmp_path, now_ms=NOW_MS, labelled=True) == []
    assert bad.exists() and missing.exists() and analysing.exists()


def test_purge_labelled_mode(tmp_path: Path) -> None:
    labelled = _session(tmp_path, "gg", age_ms=MIN_MS, label={"kind": "real"})
    unlabelled = _session(tmp_path, "hh", age_ms=120 * MIN_MS)
    assert purge(tmp_path, now_ms=NOW_MS, labelled=True) == ["gg"]
    assert not labelled.exists()
    assert unlabelled.exists()


def test_app_purges_on_start(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    stale = _session(data_dir, "ii", age_ms=120 * MIN_MS)
    labelled = _session(data_dir, "jj", age_ms=120 * MIN_MS, label={"kind": "real"})
    settings = Settings(agent_passcode="pc", data_dir=data_dir, fake_analysis=True)
    with TestClient(create_app(settings, clock=lambda: NOW_MS)):
        assert not stale.exists()
        assert labelled.exists()


REPO_ROOT = Path(__file__).resolve().parents[3]


def _run_cli(data_dir: Path, *args: str, stdin: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "scripts/purge.py", *args, "--data", str(data_dir)],
        input=stdin,
        text=True,
        capture_output=True,
        cwd=REPO_ROOT,
    )


def test_cli_all_volunteers_needs_typed_delete(tmp_path: Path) -> None:
    folder = _session(tmp_path, "kk", age_ms=MIN_MS, label={"kind": "real"})
    refused = _run_cli(tmp_path, "--all-volunteers", stdin="nope\n")
    assert refused.returncode == 1
    assert folder.exists()
    confirmed = _run_cli(tmp_path, "--all-volunteers", stdin="DELETE\n")
    assert confirmed.returncode == 0
    assert not folder.exists()


def test_cli_demo_purge(tmp_path: Path) -> None:
    created_ms = int(time.time() * 1000) - 120 * MIN_MS
    folder = tmp_path / "ll"
    folder.mkdir()
    body = {"created_at_ms": created_ms, "label": None, "state": "done"}
    (folder / "session.json").write_text(json.dumps(body), encoding="utf-8")
    result = _run_cli(tmp_path)
    assert result.returncode == 0
    assert not folder.exists()
