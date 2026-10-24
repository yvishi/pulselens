"""Golden test: pins today's analysis results and fused decisions on synthetic sessions.

A refactor must not change behaviour silently. After an intended change, regenerate with
PULSE_UPDATE_GOLDEN=1 and review the diff of golden.json.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from pulselens.analysis import analyze
from pulselens.analysis.vision import arcface, sbi
from pulselens.bundle import load_bundle
from pulselens.engine.fusion import fuse
from pulselens.engine.integrity import check_integrity
from tests.fixtures.synth import make_session

GOLDEN = Path(__file__).with_name("golden.json")

CASES: dict[str, dict] = {
    "genuine": {"kind": "genuine"},
    "replay": {"kind": "replay"},
    "swap": {"kind": "swap_no_face_echo"},
    "virtual": {"kind": "virtual_camera"},
    "genuine_15fps": {"kind": "genuine", "fps": 15.0},
    "genuine_noisy": {"kind": "genuine", "noise": 0.06, "seed": 3},
    "wrong_turn": {"kind": "genuine", "turn": "right", "turn_performed": "left"},
    "swapped_colours": {"kind": "genuine", "swap_colours": True},
}


def snapshot(path: Path) -> dict:
    """Results and fused decision of one session bundle, without clocks (decided_at_ms) and free text."""
    bundle = load_bundle(path)
    results = check_integrity(bundle) + analyze(path)
    decision = fuse(results, bundle.plan, int(bundle.session.get("attempt", 1)), decided_at_ms=0)
    return {
        "results": [
            {
                "check_id": r.check_id,
                "status": r.status,
                "risk": None if r.risk is None else round(r.risk, 9),
                "flag": r.flag,
                "reason_codes": list(r.reason_codes),
            }
            for r in results
        ],
        "decision": {"outcome": decision.outcome, "step_up": decision.step_up, "reasons": list(decision.reasons)},
    }


def test_golden_unchanged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Pinned without the SBI weights and the ArcFace model (research-only, installed per machine), so it is the same
    # on every machine.
    monkeypatch.setattr(sbi, "get_model", lambda: None)
    monkeypatch.setattr(arcface, "get_model", lambda: None)
    snaps = {name: snapshot(make_session(tmp_path / name, **kw)) for name, kw in CASES.items()}
    if os.environ.get("PULSE_UPDATE_GOLDEN") == "1":
        GOLDEN.write_text(json.dumps(snaps, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        pytest.skip("golden updated")
    if not GOLDEN.exists():
        pytest.fail(f"{GOLDEN.name} is missing; create it with PULSE_UPDATE_GOLDEN=1 pytest {Path(__file__).name}")
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    for name, snap in snaps.items():
        assert name in golden, f"{name}: not in golden.json"
        assert snap == golden[name], f"{name}: analysis or decision changed"
