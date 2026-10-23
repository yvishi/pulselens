"""Turn a recorded session bundle into a .y4m file for Chromium's fake camera (Y10 replay e2e only).

    python web/e2e/support/bundle_to_y4m.py <session_dir> <out.y4m> [--fps 30]

Reads `frames.jsonl` and `frames/{idx:06d}.jpg` (docs/CONTRACT.md section 5) in idx order and writes a 4:2:0 y4m
at a constant rate: output frame k shows the last recorded frame with t_ms <= t0 + k * 1000 / fps, so frames are
duplicated or dropped to follow the recorded timing. The default rate is the recording's median, so a steady
recording plays with no repeated frames (which the integrity checks would flag); --fps overrides it.
A frame whose JPEG is missing or unreadable repeats the previous one.
Chromium loops the file, so the replay plays again and again.

The output holds a real face: write it under data/ (gitignored) and never commit it (AGENTS.md rule 8).
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

import cv2
import numpy as np


def load_frames(session_dir: Path) -> list[dict]:
    """Frame metadata sorted by idx, one entry per idx (a re-sent batch can repeat lines)."""
    by_idx: dict[int, dict] = {}
    for line in (session_dir / "frames.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            meta = json.loads(line)
            by_idx.setdefault(int(meta["idx"]), meta)
    return [by_idx[i] for i in sorted(by_idx)]


def schedule(t_ms: list[float], fps: float) -> list[int]:
    """For each output frame at a constant rate, the index (into t_ms) of the frame on screen at that time."""
    step = 1000.0 / fps
    out: list[int] = []
    j = 0
    k = 0
    while True:
        t = t_ms[0] + k * step
        if t > t_ms[-1]:
            break
        while j + 1 < len(t_ms) and t_ms[j + 1] <= t:
            j += 1
        out.append(j)
        k += 1
    return out


def median_fps(t_ms: list[float]) -> int:
    """The recording's typical frame rate, rounded to a whole number (at least 1)."""
    interval = statistics.median(b - a for a, b in zip(t_ms, t_ms[1:], strict=False))
    return max(1, round(1000 / interval)) if interval > 0 else 30


def convert(session_dir: Path, out: Path, fps: float | None = None) -> tuple[int, int, int, float]:
    """Write the y4m; returns (output frames, width, height, fps)."""
    frames = load_frames(session_dir)
    if len(frames) < 2:
        raise ValueError(f"{session_dir} has fewer than 2 frames")
    t_ms = [float(f["t_ms"]) for f in frames]
    fps = fps or median_fps(t_ms)
    w, h = int(frames[0]["w"]) // 2 * 2, int(frames[0]["h"]) // 2 * 2
    order = schedule(t_ms, fps)
    num, den = (int(fps), 1) if float(fps).is_integer() else (round(fps * 1000), 1000)
    out.parent.mkdir(parents=True, exist_ok=True)
    cache: tuple[int, bytes] | None = None
    last = cv2.cvtColor(np.zeros((h, w, 3), np.uint8), cv2.COLOR_BGR2YUV_I420).tobytes()
    with out.open("wb") as f:
        f.write(f"YUV4MPEG2 W{w} H{h} F{num}:{den} Ip A1:1 C420jpeg\n".encode())
        for j in order:
            if cache is None or cache[0] != j:
                img = cv2.imread(str(session_dir / "frames" / f"{int(frames[j]['idx']):06d}.jpg"), cv2.IMREAD_COLOR)
                if img is not None:
                    if img.shape[:2] != (h, w):
                        img = cv2.resize(img, (w, h))
                    last = cv2.cvtColor(img, cv2.COLOR_BGR2YUV_I420).tobytes()
                cache = (j, last)
            f.write(b"FRAME\n")
            f.write(cache[1])
    return len(order), w, h, fps


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("session_dir", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--fps", type=float, default=None, help="output rate (default: the recording's median)")
    args = parser.parse_args(argv)
    if args.fps is not None and args.fps <= 0:
        parser.error("--fps must be positive")
    try:
        n, w, h, fps = convert(args.session_dir, args.out, args.fps)
    except (OSError, ValueError, KeyError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(f"{args.out}: {n} frames, {w}x{h} at {fps:g} fps")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
