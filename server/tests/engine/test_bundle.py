"""bundle.py round trip and tolerance (CONTRACT 5)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pulselens.bundle import load_bundle, write_bundle
from pulselens.contracts import ChallengeEvent, FrameMeta


def _jpeg(w: int = 8, h: int = 6) -> bytes:
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    ok, buf = cv2.imencode(".jpg", np.full((h, w, 3), 128, dtype=np.uint8))
    assert ok
    return buf.tobytes()


def _event(step: str) -> ChallengeEvent:
    return ChallengeEvent(step_id=step, status="shown", painted_t_ms=10.0, ended_t_ms=410.0, shown_rgb=(0.5, 0.4, 0.3))


def test_roundtrip(tmp_path: Path) -> None:
    jpeg = _jpeg()
    frames = [(FrameMeta(idx=i, t_ms=33.3 * i, w=8, h=6), jpeg) for i in (2, 0, 1)]
    write_bundle(tmp_path, session={"session_id": "s1"}, preflight=None, plan=None, challenge=None,
                 frames=frames, events=[_event("c0"), _event("c1")])
    b = load_bundle(tmp_path)
    assert [f.idx for f in b.frames] == [0, 1, 2]
    assert [e.step_id for e in b.events] == ["c0", "c1"]
    img = b.read_frame(1)
    assert img is not None and img.shape == (6, 8, 3)


def test_missing_optional_files(tmp_path: Path) -> None:
    (tmp_path / "session.json").write_text(json.dumps({"session_id": "s1"}), encoding="utf-8")
    b = load_bundle(tmp_path)
    assert b.preflight is None and b.plan is None and b.challenge is None and b.label is None
    assert b.frames == [] and b.events == []
    assert b.read_frame(0) is None


def test_engine_bookkeeping_and_bad_lines_never_lose_the_session(tmp_path: Path) -> None:
    (tmp_path / "session.json").write_text(json.dumps({"session_id": "s1"}), encoding="utf-8")
    good = {"idx": 0, "t_ms": 0.0, "w": 8, "h": 6, "batch_seq": 0, "received_at_ms": 1}
    lines = [json.dumps(good), "{not json", "[1]", json.dumps({"idx": "x"})]
    (tmp_path / "frames.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    b = load_bundle(tmp_path)
    assert [f.idx for f in b.frames] == [0]
    assert b.skipped_lines == 3


def test_corrupt_jpeg_reads_as_none(tmp_path: Path) -> None:
    write_bundle(tmp_path, session={}, preflight=None, plan=None, challenge=None,
                 frames=[(FrameMeta(idx=0, t_ms=0.0, w=8, h=6), b"not a jpeg")], events=[])
    pytest.importorskip("cv2")
    assert load_bundle(tmp_path).read_frame(0) is None


def test_empty_jpeg_reads_as_none(tmp_path: Path) -> None:
    """Issue #5: a 0-byte frame file made cv2.imdecode assert instead of returning None."""
    pytest.importorskip("cv2")
    write_bundle(tmp_path, session={}, preflight=None, plan=None, challenge=None,
                 frames=[(FrameMeta(idx=0, t_ms=0.0, w=8, h=6), b""), (FrameMeta(idx=1, t_ms=33.3, w=8, h=6), _jpeg())],
                 events=[])
    b = load_bundle(tmp_path)
    assert b.read_frame(0) is None
    assert b.read_frame(1) is not None
