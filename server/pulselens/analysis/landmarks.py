"""The landmarks cache, <bundle>/landmarks.jsonl (CONTRACT section 5): the only file the analysis writes.

One line per frame: {idx, landmarks: [[x, y, z] x 478] normalised, or null, yaw, pitch}. A present cache is used
as is, so synthetic bundles ship one and tests never need the face model.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import cv2

from pulselens.bundle import Bundle
from pulselens.config import ROOT

FACE_MODEL = ROOT / "models" / "mediapipe" / "face_landmarker.task"
CACHE_NAME = "landmarks.jsonl"

log = logging.getLogger("pulselens.analysis")


def read_cache(path: Path) -> dict[int, dict | None] | None:
    """{idx: {landmarks, yaw, pitch} or None}, or None when there is no cache. Unreadable lines are skipped."""
    path = Path(path) / CACHE_NAME
    if not path.exists():
        return None
    out: dict[int, dict | None] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
            idx = int(row["idx"])
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            continue
        lm = row.get("landmarks")
        out[idx] = {"landmarks": lm, "yaw": row.get("yaw"), "pitch": row.get("pitch")} if lm else None
    return out


def write_cache(path: Path, found: dict[int, dict | None]) -> None:
    lines = []
    for idx in sorted(found):
        d = found[idx] or {}
        lines.append(json.dumps({"idx": idx, "landmarks": d.get("landmarks"), "yaw": d.get("yaw"),
                                 "pitch": d.get("pitch")}))
    (Path(path) / CACHE_NAME).write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")


def landmarks_for(bundle: Bundle, model_path: Path = FACE_MODEL) -> dict[int, dict | None]:
    """The cache if present; else runs the landmarker over every frame (VIDEO mode, at each frame's t_ms) and writes
    the cache. Without the model every frame has no face, and nothing is cached (so a later run with it can retry)."""
    cached = read_cache(bundle.path)
    if cached is not None:
        return cached
    if not model_path.exists():
        log.warning("%s is missing (run scripts/fetch_models.py); every face check will abstain", model_path)
        return {f.idx: None for f in bundle.frames}
    from pulselens.analysis.context import read_frame
    from pulselens.analysis.vision.face import Landmarker

    found: dict[int, dict | None] = {}
    landmarker = Landmarker(model_path)
    try:
        for meta in bundle.frames:
            img = read_frame(bundle, meta.idx)
            found[meta.idx] = landmarker.detect(cv2.cvtColor(img, cv2.COLOR_BGR2RGB), meta.t_ms) if img is not None \
                else None
    finally:
        landmarker.close()
    try:
        write_cache(bundle.path, found)
    except OSError:
        log.warning("could not write %s", bundle.path / CACHE_NAME)
    return found
