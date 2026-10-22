"""eval/convert_v2.py on a tiny synthetic bundle in the old prototype's format (no real faces)."""

from __future__ import annotations

import json
from pathlib import Path

from eval.convert_v2 import convert
from pulselens.bundle import load_bundle

JPEG = b"\xff\xd8\xff\xd9"


def old_bundle(root: Path, *, finished: bool = True, label: dict | None = None) -> Path:
    src = root / "abcdef0123456789"
    (src / "frames").mkdir(parents=True)
    frames = [{"i": i, "t": 27_000.0 + 64 * i, "capture_time": None, "presented_frames": i, "w": 640, "h": 480,
               "file": f"{i:06d}.jpg"} for i in range(100)]
    for f in frames:
        (src / "frames" / f["file"]).write_bytes(JPEG)
    (src / "frames.jsonl").write_text("".join(json.dumps(f) + "\n" for f in frames), encoding="utf-8")

    def pulse(k: int, mode: str, hue: float | None, painted: float | None, ok: bool = True) -> dict:
        return {"pulse_id": f"x-{k}", "kind": "light", "params": {"mode": mode, "hue_deg": hue, "duration_ms": 600},
                "painted": painted, "ended": None if painted is None else painted + 605, "ok": ok,
                "shown": {"neutral": [188, 188, 188], "rgb": [250, 163, 185]}, "error": None if ok else "no_ack"}

    pulses = [pulse(0, "colour", 0.0, 28_000.0), pulse(1, "white", None, 29_500.0), pulse(2, "colour", 120.0, 31_000.0),
              pulse(3, "colour", 240.0, None, ok=False)]
    (src / "pulses.jsonl").write_text("".join(json.dumps(p) + "\n" for p in pulses), encoding="utf-8")
    probe = [{"step": 0, "request": {"width": 1280, "height": 720, "frameRate": 30}, "skipped": False, "ok": True,
              "apply_start": 27_100.0, "first_match_t": 27_850.0, "missing_frames": 2,
              "settings_after": {"width": 1280, "height": 720}},
             {"step": 2, "request": {"width": 1000, "height": 750, "frameRate": 24}, "skipped": False, "ok": False,
              "apply_start": 27_900.0, "first_match_t": None, "missing_frames": None, "settings_after": {}}]
    (src / "probe.jsonl").write_text("".join(json.dumps(p) + "\n" for p in probe), encoding="utf-8")
    meta = {"session_id": src.name, "created_ms": 1_800_000_000_000, "label": label,
            "camera_details": {"browser": "Brave 155", "os": "Windows 11", "camera_label": "USB2.0 HD UVC WebCam",
                               "fps_median": 15.6, "clock_source": "captureTime",
                               "settings": {"width": 640, "height": 480}, "capabilities": {"exposureMode": []}}}
    if finished:
        meta["finalize"] = {"frames": 100, "dropped": 0}
    (src / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return src


def test_converts_frames_steps_events_probe_and_label(tmp_path: Path) -> None:
    label = {"person": "P01", "device": "D01", "light": "normal", "kind": "attack", "tool": "liveswap",
             "consent_ref": "C-01"}
    out = convert(old_bundle(tmp_path / "old", label=label), tmp_path / "new")
    b = load_bundle(out)
    assert out.name == "abcdef0123456789" and len(b.frames) == 100
    assert b.frames[0].t_ms == 0.0 and b.frames[1].t_ms == 64.0  # ms since the first frame
    assert [s.hue_deg for s in b.challenge.steps] == [0, 120, 240]  # white pulses left out
    assert b.challenge.baseline_ms == 1000 and b.challenge.steps[1].start_offset_ms == 3000
    assert [e.status for e in b.events] == ["shown", "shown", "skipped"]
    assert b.events[0].painted_t_ms == 1000.0 and b.events[0].shown_rgb == (250 / 255, 163 / 255, 185 / 255)
    assert (b.plan.mode, b.plan.run_light, b.plan.run_turn) == ("CONSTRAINED", True, False)
    assert b.preflight.measured_fps == 15.6 and b.preflight.clock == "captureTime"
    assert [p.accepted for p in b.preflight.probe] == [True, False] and b.preflight.probe[0].switch_ms == 750.0
    assert (b.label.kind, b.label.tool, b.label.set) == ("live_swap", "deep_live_cam", "A")
    rows = [json.loads(line) for line in (out / "frames.jsonl").read_text().splitlines()]
    assert b.session["converted_from"] == "v2" and {r["batch_seq"] for r in rows} == {0, 1, 2, 3}


def test_genuine_label_has_no_tool(tmp_path: Path) -> None:
    label = {"person": "P01", "device": "D01", "light": "dim", "kind": "genuine", "tool": None, "consent_ref": "C"}
    b = load_bundle(convert(old_bundle(tmp_path / "old", label=label), tmp_path / "new"))
    assert (b.label.kind, b.label.tool, b.label.light) == ("genuine", None, "dim")


def test_unfinished_session_is_skipped(tmp_path: Path) -> None:
    assert convert(old_bundle(tmp_path / "old", finished=False), tmp_path / "new") is None
