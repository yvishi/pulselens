"""Ingest an external video file as a PulseLens session bundle and run analysis.

Usage:
    python scripts/ingest_video.py <video_path> [--label-kind KIND] [--label-tool TOOL] [--data-dir PATH]
"""

from __future__ import annotations

import argparse
import colorsys
import json
import math
import secrets
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

from pulselens.bundle import write_bundle  # noqa: E402
from pulselens.config import get_settings, load_config  # noqa: E402
from pulselens.contracts import (  # noqa: E402
    ChallengeEvent,
    ColourStep,
    DigitStep,
    FrameBatchMeta,
    FrameMeta,
    Label,
    NodStep,
    Preflight,
    TurnStep,
)
from pulselens.engine import audit  # noqa: E402
from pulselens.engine.planner import make_challenge, plan_session, rng_for_nonce  # noqa: E402
from pulselens.engine.runner import run_analysis  # noqa: E402
from pulselens.engine.store import SessionStore  # noqa: E402


def _read_video_frames(path: Path) -> tuple[float, list[cv2.typing.MatLike]]:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise ValueError(f"Could not open video file: {path}")

    fps = float(cap.get(cv2.CAP_PROP_FPS))
    if fps <= 0 or fps > 120 or math.isnan(fps):
        fps = 30.0

    frames = []
    while True:
        ret, frame = cap.read()
        if not ret or frame is None:
            break
        frames.append(frame)
    cap.release()

    if not frames:
        raise ValueError(f"No frames could be read from {path}")
    return fps, frames


def ingest_video(
    video_path: Path,
    *,
    data_dir: Path | None = None,
    product: str = "savings_account",
    label_kind: str | None = None,
    label_tool: str | None = None,
    session_id: str | None = None,
    fake_analysis: bool = False,
) -> Path:
    video_path = Path(video_path).resolve()
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    settings = get_settings()
    root_data = Path(data_dir) if data_dir is not None else settings.data_dir
    root_data.mkdir(parents=True, exist_ok=True)

    fps, raw_frames = _read_video_frames(video_path)
    h, w = raw_frames[0].shape[:2]

    sid = session_id or secrets.token_hex(8)
    nonce = secrets.token_hex(16)
    cfg = load_config()

    preflight = Preflight(
        user_agent="judge_video",
        platform="desktop",
        browser="file_ingest",
        camera_label="video_upload",
        width=w,
        height=h,
        measured_fps=round(fps, 1),
        dropped_frame_ratio=0.0,
        blur=0.0,
        brightness=120.0,
        face_found=True,
        face_fraction=0.1,
        controls=[],
        gyro=False,
        no_flash_requested=False,
        clock="captureTime",
        probe=[],
    )

    plan = plan_session(preflight, session_no_flash=False, cfg=cfg)
    rng = rng_for_nonce(nonce)
    challenge = make_challenge(plan, sid, nonce, rng, cfg)

    # If video is shorter than challenge span, loop frames to cover challenge duration
    target_ms = challenge.total_ms + 1000
    frame_ms = 1000.0 / fps
    needed_count = max(len(raw_frames), int(math.ceil(target_ms / frame_ms)))
    max_cap = cfg.get("session", {}).get("max_frames", 900)
    total_frames = min(needed_count, max_cap)

    encoded_frames: list[tuple[FrameMeta, bytes]] = []
    for idx in range(total_frames):
        src_img = raw_frames[idx % len(raw_frames)]
        t_ms = idx * frame_ms
        ok, buf = cv2.imencode(".jpg", src_img, [cv2.IMWRITE_JPEG_QUALITY, 90])
        if ok and buf is not None:
            encoded_frames.append((FrameMeta(idx=idx, t_ms=t_ms, w=w, h=h), buf.tobytes()))

    events: list[ChallengeEvent] = []
    for s in challenge.steps:
        if isinstance(s, ColourStep):
            r, g, b = colorsys.hsv_to_rgb(s.hue_deg / 360.0, 1.0, 1.0)
            events.append(
                ChallengeEvent(
                    step_id=s.step_id,
                    status="shown",
                    painted_t_ms=float(challenge.baseline_ms + s.start_offset_ms),
                    ended_t_ms=float(challenge.baseline_ms + s.start_offset_ms + s.dwell_ms),
                    shown_rgb=(r, g, b),
                )
            )
        elif isinstance(s, TurnStep | NodStep | DigitStep):  # every prompt "shown" on schedule
            events.append(
                ChallengeEvent(
                    step_id=s.step_id,
                    status="shown",
                    painted_t_ms=float(challenge.baseline_ms + s.start_offset_ms),
                    ended_t_ms=float(challenge.baseline_ms + s.start_offset_ms + s.duration_ms),
                    shown_rgb=None,
                )
            )

    created_at = int(time.time() * 1000)
    label = (
        Label(
            person="P00",
            device="D00",
            light="normal",
            kind=label_kind or "replay_screen",
            tool=label_tool or "phone_screen",
            set="A",
            consent_ref="judge_provided",
        )
        if label_kind
        else None
    )

    session = {
        "session_id": sid,
        "nonce": nonce,
        "product": product,
        "no_flash": False,
        "attempt": 1,
        "previous_session_id": None,
        "created_at_ms": created_at,
        "expires_at_ms": created_at + 15 * 60_000,
        "state": "analysing",
        "label": label.model_dump() if label else None,
        "ingested_from": str(video_path),
    }

    out = root_data / sid
    if out.exists():
        shutil.rmtree(out)

    write_bundle(
        out,
        session=session,
        preflight=preflight,
        plan=plan,
        challenge=challenge,
        frames=encoded_frames,
        events=events,
    )

    # Add engine batch numbers and received timestamps for integrity check
    rows = [
        {**m.model_dump(), "batch_seq": i // 30, "received_at_ms": created_at}
        for i, (m, _) in enumerate(encoded_frames)
    ]
    (out / "frames.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")

    # Audit chain
    audit.append(out, "session.created", session)
    audit.append(out, "challenge.issued", challenge.model_dump(mode="json"))

    # Batches audit
    for batch_i in range(0, len(encoded_frames), 30):
        batch = encoded_frames[batch_i : batch_i + 30]
        meta = FrameBatchMeta(
            batch_seq=batch_i // 30,
            frames=[m for m, _ in batch],
        )
        jpegs = b"".join(j for _, j in batch)
        audit.append(out, "frames.batch", jpegs + meta.model_dump_json().encode())

    audit.append(out, "events.received", "".join(e.model_dump_json() + "\n" for e in events).encode())

    # Run analysis
    store = SessionStore(root_data)
    with ThreadPoolExecutor(max_workers=1) as pool:
        run_analysis(out, store, pool=pool, fake=fake_analysis)

    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest video into a PulseLens session.")
    parser.add_argument("video_path", type=Path, help="Path to video file")
    parser.add_argument("--data-dir", type=Path, default=None, help="Root sessions directory")
    parser.add_argument("--product", type=str, default="savings_account", help="Product name")
    parser.add_argument("--label-kind", type=str, default=None, help="Optional ground-truth attack kind")
    parser.add_argument("--label-tool", type=str, default=None, help="Optional tool name")
    parser.add_argument("--fake-analysis", action="store_true", help="Use fake analysis instead of real checks")
    args = parser.parse_args(argv)

    out = ingest_video(
        args.video_path,
        data_dir=args.data_dir,
        product=args.product,
        label_kind=args.label_kind,
        label_tool=args.label_tool,
        fake_analysis=args.fake_analysis,
    )
    print(f"Session created: {out.name}")
    print(f"Path: {out}")
    print(f"Console URL: http://localhost:5173/console/{out.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
