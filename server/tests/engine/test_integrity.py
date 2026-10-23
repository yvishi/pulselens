"""K5: ingest integrity (integrity.protocol and integrity.coverage)."""

from __future__ import annotations

import json
from pathlib import Path

from pulselens.bundle import load_bundle, write_bundle
from pulselens.config import load_config
from pulselens.contracts import ChallengeEvent, ColourStep, FrameMeta, Plan
from pulselens.engine.integrity import check_integrity
from pulselens.engine.planner import make_challenge, rng_for_nonce
from pulselens.engine.reason_text import REASON_TEXT

JPEG = b"\xff\xd8\xff\xd9"
CODES = ["integrity.non_monotonic_time", "integrity.duplicate_index", "integrity.unknown_step",
         "integrity.event_order", "integrity.after_complete", "integrity.no_challenge", "integrity.too_few_frames",
         "integrity.batch_gaps"]


def make(tmp_path: Path, *, n: int = 300, fps: float = 30.0, challenge: bool = True, batch: int = 30,
         rows: list[dict] | None = None, events: list[ChallengeEvent] | None = None, session: dict | None = None):
    """A clean CAPABLE session: n frames, every step shown in order. Returns the bundle path."""
    plan = Plan(mode="CAPABLE", run_light=True, run_turn=True, agent_questions=False, reasons=["mode.capable.ok"])
    ch = make_challenge(plan, "s1", "nonce", rng_for_nonce("nonce"), load_config()) if challenge else None
    frames = [(FrameMeta(idx=i, t_ms=i * 1000 / fps, w=640, h=480), JPEG) for i in range(n)]
    if events is None and ch is not None:
        events = []
        for s in ch.steps:
            start = ch.baseline_ms + s.start_offset_ms
            length = s.dwell_ms if isinstance(s, ColourStep) else s.duration_ms
            rgb = (0.6, 0.5, 0.3) if isinstance(s, ColourStep) else None
            events.append(ChallengeEvent(step_id=s.step_id, status="shown", painted_t_ms=start + 5.0,
                                         ended_t_ms=start + length, shown_rgb=rgb))
    write_bundle(tmp_path, session={"session_id": "s1", **(session or {})}, preflight=None, plan=plan, challenge=ch,
                 frames=frames, events=events or [])
    if rows is None:
        rows = [{**m.model_dump(), "batch_seq": i // batch, "received_at_ms": 0} for i, (m, _) in enumerate(frames)]
    (tmp_path / "frames.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return tmp_path


def run(path: Path):
    protocol, coverage = check_integrity(load_bundle(path))
    assert (protocol.check_id, coverage.check_id) == ("integrity.protocol", "integrity.coverage")
    assert protocol.family == coverage.family == "B" and protocol.vote_group == coverage.vote_group == "B.protocol"
    return protocol, coverage


def test_clean_bundle_is_usable(tmp_path: Path) -> None:
    protocol, coverage = run(make(tmp_path))
    assert (protocol.status, protocol.risk, protocol.flag) == ("usable", 0.0, False)
    assert (coverage.status, coverage.risk, coverage.flag) == ("usable", 0.0, False)
    assert coverage.features["frames"] == 300 and coverage.features["batch_gaps"] == 0
    assert coverage.features["frames_per_step_window"] > 0
    assert "300 frames" in coverage.explanation


def test_non_monotonic_time(tmp_path: Path) -> None:
    rows = [{"idx": i, "t_ms": 100.0 * i, "w": 640, "h": 480, "batch_seq": 0, "received_at_ms": 0} for i in range(60)]
    rows[30]["t_ms"] = 5.0
    protocol, _ = run(make(tmp_path, rows=rows))
    assert protocol.status == "protocol_error" and protocol.reason_codes == ["integrity.non_monotonic_time"]


def test_duplicate_index(tmp_path: Path) -> None:
    rows = [{"idx": i, "t_ms": 33.3 * i, "w": 640, "h": 480, "batch_seq": i // 30, "received_at_ms": 0}
            for i in range(60)]
    rows.append({**rows[10], "batch_seq": 2})
    protocol, _ = run(make(tmp_path, rows=rows))
    assert protocol.status == "protocol_error" and "integrity.duplicate_index" in protocol.reason_codes


def test_unknown_step(tmp_path: Path) -> None:
    ev = [ChallengeEvent(step_id="c9", status="shown", painted_t_ms=10.0, ended_t_ms=400.0, shown_rgb=(1, 1, 1))]
    protocol, _ = run(make(tmp_path, events=ev))
    assert protocol.reason_codes == ["integrity.unknown_step"]


def test_event_order(tmp_path: Path) -> None:
    ev = [ChallengeEvent(step_id="c1", status="shown", painted_t_ms=100.0, ended_t_ms=500.0, shown_rgb=(1, 0, 0)),
          ChallengeEvent(step_id="c0", status="shown", painted_t_ms=900.0, ended_t_ms=1300.0, shown_rgb=(0, 1, 0))]
    protocol, _ = run(make(tmp_path, events=ev))
    assert protocol.reason_codes == ["integrity.event_order"]


def test_skipped_steps_do_not_count_for_order(tmp_path: Path) -> None:
    ev = [ChallengeEvent(step_id="c1", status="shown", painted_t_ms=100.0, ended_t_ms=500.0, shown_rgb=(1, 0, 0)),
          ChallengeEvent(step_id="c0", status="skipped", painted_t_ms=None, ended_t_ms=None, shown_rgb=None,
                         skip_reason="fps_drop")]
    protocol, _ = run(make(tmp_path, events=ev))
    assert protocol.status == "usable"


def test_after_complete(tmp_path: Path) -> None:
    protocol, _ = run(make(tmp_path, session={"after_complete_attempts": 1}))
    assert protocol.reason_codes == ["integrity.after_complete"]


def test_no_challenge(tmp_path: Path) -> None:
    protocol, _ = run(make(tmp_path, challenge=False))
    assert protocol.reason_codes == ["integrity.no_challenge"]


def test_several_broken_rules_list_every_code(tmp_path: Path) -> None:
    protocol, _ = run(make(tmp_path, challenge=False, session={"after_complete_attempts": 2}))
    assert protocol.reason_codes == ["integrity.no_challenge", "integrity.after_complete"]
    assert protocol.explanation == " ".join(REASON_TEXT[c] for c in protocol.reason_codes)


def test_network_gap_is_not_protocol_error(tmp_path: Path) -> None:
    rows = [{"idx": i, "t_ms": 33.3 * i, "w": 640, "h": 480, "batch_seq": seq, "received_at_ms": 0}
            for i, seq in zip(range(120), [0] * 30 + [1] * 30 + [3] * 60, strict=True)]
    protocol, coverage = run(make(tmp_path, rows=rows))
    assert protocol.status == "usable"
    assert coverage.status == "usable" and coverage.features["batch_gaps"] == 1
    assert coverage.risk == 0.25 and coverage.flag  # 1 of 4 batches missing ≥ 0.2
    assert "1 of 4 upload batches missing" in coverage.explanation


def test_small_gap_is_noted_not_flagged(tmp_path: Path) -> None:
    seqs = [k // 10 for k in range(110) if k // 10 != 4]  # batch 4 of 11 missing
    rows = [{"idx": i, "t_ms": 33.3 * i, "w": 640, "h": 480, "batch_seq": seq, "received_at_ms": 0}
            for i, seq in enumerate(seqs)]
    _, coverage = run(make(tmp_path, rows=rows))
    assert coverage.risk == 1 / 11 and not coverage.flag


def test_too_few_frames_abstains(tmp_path: Path) -> None:
    _, coverage = run(make(tmp_path, n=49))
    assert coverage.status == "abstain" and coverage.reason_codes == ["integrity.too_few_frames"]
    assert coverage.risk is None and not coverage.flag


def test_empty_bundle_never_raises(tmp_path: Path) -> None:
    (tmp_path / "session.json").write_text("{}", encoding="utf-8")
    protocol, coverage = run(tmp_path)
    assert protocol.status == "usable" and coverage.status == "abstain"


def test_every_integrity_code_has_text() -> None:
    assert [c for c in CODES if c not in REASON_TEXT] == []
