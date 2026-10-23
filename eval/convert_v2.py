"""Convert recordings from the old prototype (PulseLensV2 / PulseLensFinal bundles) into this repo's bundle format.

    python -m eval.convert_v2 --src ../PulseLensV2/data/sessions --dst data/converted

Local only: the recordings are volunteer data and never go into git (`data/` is gitignored). The converted bundle
keeps the session id, the JPEGs as recorded and the label; frame and event times become ms since the first frame.

What maps and what does not:
- Each painted colour pulse becomes a ColourStep (hue and duration as shown) with its ChallengeEvent. White pulses
  have no colour direction and are left out. The old prototype had no head turn, so the plan runs no turn.
- The mode probe becomes Preflight.probe. Values the old prototype did not keep (blur, face fraction) are 0 and
  `face_found` is true: the planner is not re-run, so they decide nothing.
- The old 0-degree hue (saturated red) is kept as recorded: it is history, not a new challenge.
- Unfinished sessions (no `finalize` in meta.json) are skipped.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from pulselens.bundle import frame_name, write_bundle
from pulselens.contracts import Challenge, ChallengeEvent, ColourStep, FrameMeta, Label, ModeProbe, Plan, Preflight

KIND = {"screen_replay": "replay_screen", "premade_injection": "virtual_camera", "liveswap": "live_swap",
        "liveportrait": "photo_animation", "emulator": "virtual_camera"}
TOOL = {"screen_replay": "phone_screen", "premade_injection": "obs", "liveswap": "deep_live_cam",
        "liveportrait": "liveportrait", "emulator": "android_emulator"}
CLOCK = {"captureTime": "captureTime"}  # rvfc, videoframe and raf all map to "now"
NONCE = "converted-from-v2"


def _jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _label(old: dict[str, Any] | None) -> Label | None:
    if not old:
        return None
    tool = old.get("tool")
    kind = "genuine" if old.get("kind") == "genuine" else KIND.get(tool or "", "live_swap")
    light = old.get("light") if old.get("light") in ("bright", "normal", "dim", "tube") else "normal"
    return Label(person=old["person"], device=old["device"], light=light, kind=kind,
                 tool=None if kind == "genuine" else TOOL.get(tool or ""), set="A", consent_ref=old["consent_ref"])


def _probe(rows: list[dict[str, Any]]) -> list[ModeProbe]:
    out = []
    for r in rows:
        req = r.get("request") or {}
        if r.get("skipped") or not req:
            continue
        after = r.get("settings_after") or {}
        delivered = (int(after["width"]), int(after["height"])) if r.get("ok") and "width" in after else None
        switch = (r["first_match_t"] - r["apply_start"]) if r.get("first_match_t") and r.get("apply_start") else None
        out.append(ModeProbe(requested=(int(req["width"]), int(req["height"]), int(req.get("frameRate", 30))),
                             accepted=bool(r.get("ok")), delivered=delivered, switch_ms=switch,
                             frames_missing=r.get("missing_frames")))
    return out


def _platform(os_name: str) -> str:
    low = os_name.lower()
    return "android" if "android" in low else "ios" if "ios" in low or "iphone" in low else "desktop"


def _steps_and_events(pulses: list[dict[str, Any]], t0: float) -> tuple[int, list[ColourStep], list[ChallengeEvent]]:
    """Painted colour pulses → (baseline_ms, steps, events). Times become ms since the first frame; steps start
    after the baseline (the first painted colour). A pulse that was never painted keeps its place 1 s after the
    previous step: the old prototype logged no time for it, and integrity only needs the order."""
    painted = [p["painted"] for p in pulses if p.get("painted") is not None]
    baseline = int(round(min(painted) - t0)) if painted else 0
    steps: list[ColourStep] = []
    events: list[ChallengeEvent] = []
    for k, p in enumerate(pulses):
        step_id, at = f"c{k}", p.get("painted")
        if at is not None:
            start = int(round(at - t0)) - baseline
        else:
            start = steps[-1].start_offset_ms + 1000 if steps else 0
        steps.append(ColourStep(step_id=step_id, hue_deg=int(round(p["params"].get("hue_deg") or 0)),
                                start_offset_ms=start, dwell_ms=int(p["params"].get("duration_ms", 400))))
        rgb = (p.get("shown") or {}).get("rgb")
        if p.get("ok") and at is not None:
            ended = p.get("ended")
            events.append(ChallengeEvent(step_id=step_id, status="shown", painted_t_ms=at - t0,
                                         ended_t_ms=ended - t0 if ended is not None else None,
                                         shown_rgb=tuple(c / 255 for c in rgb) if rgb else None))
        else:
            events.append(ChallengeEvent(step_id=step_id, status="skipped", painted_t_ms=None, ended_t_ms=None,
                                         shown_rgb=None, skip_reason=p.get("error") or "not_painted"))
    return baseline, sorted(steps, key=lambda st: st.start_offset_ms), events


def _plan_and_challenge(sid: str, fps: float, baseline: int, steps: list[ColourStep]) -> tuple[Plan, Challenge]:
    """What actually ran: the light if any colour was painted, never a turn (the old prototype had none)."""
    mode = "CAPABLE" if fps >= 20 else "CONSTRAINED"
    plan = Plan(mode=mode, run_light=bool(steps), run_turn=False, agent_questions=False,
                reasons=["mode.capable.ok" if mode == "CAPABLE" else "mode.constrained.fps"])
    end = max((st.start_offset_ms + st.dwell_ms for st in steps), default=0)
    return plan, Challenge(session_id=sid, nonce=NONCE, mode=mode, baseline_ms=baseline, steps=steps,
                           total_ms=end + 500)


def _preflight(cd: dict[str, Any], fin: dict[str, Any], first_frame: dict[str, Any],
               probe_rows: list[dict[str, Any]]) -> Preflight:
    settings = cd.get("settings") or {}
    return Preflight(
        user_agent=str(cd.get("browser", "")), platform=_platform(str(cd.get("os", ""))),
        browser=str(cd.get("browser", "")), camera_label=str(cd.get("camera_label", "")),
        width=int(settings.get("width", first_frame["w"])), height=int(settings.get("height", first_frame["h"])),
        measured_fps=float(cd.get("fps_median") or 0.0),
        dropped_frame_ratio=float(fin.get("dropped", 0)) / max(1, int(fin.get("frames", 1))),
        blur=0.0, brightness=0.0, face_found=True, face_fraction=0.0, controls=sorted(cd.get("capabilities") or {}),
        gyro=cd.get("gyro") in ("available", "granted"), no_flash_requested=False,
        clock=CLOCK.get(str(cd.get("clock_source")), "now"), probe=_probe(probe_rows),
    )


def _session(meta: dict[str, Any]) -> dict[str, Any]:
    created = int(meta.get("created_ms", 0))
    label = _label(meta.get("label"))
    return {"session_id": meta["session_id"], "nonce": NONCE, "product": "savings_account", "no_flash": False,
            "attempt": 1, "previous_session_id": None, "created_at_ms": created,
            "expires_at_ms": created + 15 * 60_000, "state": "analysing",
            "label": label.model_dump() if label else None, "converted_from": "v2"}


def convert(src: Path, dst: Path) -> Path | None:
    """One old bundle → one new bundle at dst/<session id>. None when the old session never finished."""
    meta = json.loads((src / "meta.json").read_text(encoding="utf-8"))
    fin = meta.get("finalize")
    frame_rows = sorted(_jsonl(src / "frames.jsonl"), key=lambda r: r.get("i", -1))
    if not fin or not frame_rows:
        return None
    sid, cd = meta["session_id"], meta.get("camera_details") or {}
    t0 = float(frame_rows[0]["t"])
    colour = [p for p in _jsonl(src / "pulses.jsonl") if (p.get("params") or {}).get("mode") == "colour"]
    baseline, steps, events = _steps_and_events(colour, t0)
    preflight = _preflight(cd, fin, frame_rows[0], _jsonl(src / "probe.jsonl"))
    plan, challenge = _plan_and_challenge(sid, preflight.measured_fps, baseline, steps)
    session = _session(meta)
    frames = []
    for r in frame_rows:
        jpeg = src / "frames" / str(r.get("file", frame_name(int(r["i"]))))
        if jpeg.exists():
            frames.append((FrameMeta(idx=int(r["i"]), t_ms=float(r["t"]) - t0, w=int(r["w"]), h=int(r["h"])),
                           jpeg.read_bytes()))
    out = dst / sid
    if out.exists():
        shutil.rmtree(out)
    write_bundle(out, session=session, preflight=preflight, plan=plan, challenge=challenge, frames=frames,
                 events=events)
    # write_bundle writes FrameMeta only; the engine's lines also carry a batch number (the old uploader's batches
    # were time-based, so 30 frames a batch stands in), which integrity needs.
    rows = [{**m.model_dump(), "batch_seq": i // 30, "received_at_ms": session["created_at_ms"]}
            for i, (m, _) in enumerate(frames)]
    (out / "frames.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", type=Path, required=True, help="the old data/sessions folder")
    ap.add_argument("--dst", type=Path, default=Path("data/converted"))
    ap.add_argument("sessions", nargs="*", help="session ids (default: every session in --src)")
    args = ap.parse_args(argv)
    ids = args.sessions or sorted(p.name for p in args.src.iterdir() if (p / "meta.json").exists())
    args.dst.mkdir(parents=True, exist_ok=True)
    for sid in ids:
        out = convert(args.src / sid, args.dst)
        print(f"{sid}: {'skipped (unfinished)' if out is None else out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
