"""What every check receives: per-frame region means in linear light, yaw and the face box, read in one pass."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np

from pulselens.analysis.landmarks import landmarks_for
from pulselens.analysis.quality import QualityReport, assess
from pulselens.analysis.thresholds import Thresholds
from pulselens.analysis.vision.face import regions_from_landmarks, to_pixels
from pulselens.analysis.vision.frames import REGION_NAMES, dhash, region_means
from pulselens.bundle import Bundle


@dataclass
class RegionSeries:
    rgb_linear: np.ndarray  # (n_frames, 3) mean linear RGB, NaN where the region is not usable
    coverage: np.ndarray  # (n_frames,) share of the region inside the frame, 0..1


@dataclass
class AnalysisContext:
    bundle: Bundle
    t: np.ndarray  # (n,) frame t_ms
    regions: dict[str, RegionSeries]  # "skin", "left_cheek", "right_cheek", "neck", "background"
    yaw: np.ndarray  # (n,) degrees, NaN without a face (CONTRACT section 1 sign)
    face_box: np.ndarray  # (n, 4) x, y, w, h in pixels, NaN without a face
    quality: QualityReport | None  # from quality.assess; build_context always fills it
    thresholds: Thresholds
    readable: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=bool))  # (n,) the JPEG decoded
    frame_w: int = 0
    # Near-duplicate inputs, against the previous readable frame (NaN for the first readable and unreadable frames):
    hamming_prev: np.ndarray = field(default_factory=lambda: np.zeros(0))  # (n,) dHash bit distance
    mad_prev: np.ndarray = field(default_factory=lambda: np.zeros(0))  # (n,) mean abs diff, 0..255, [::8] grid

    @property
    def n(self) -> int:
        return len(self.t)


def _num(x: Any) -> float:
    return float(x) if isinstance(x, int | float) and np.isfinite(x) else np.nan


def build_context(bundle: Bundle, thresholds: Thresholds) -> AnalysisContext:
    """Frames are decoded one at a time, so a 900-frame session is never all in memory. A frame that does not decode
    keeps its place in `t`, with NaN regions, yaw and face box."""
    landmarks = landmarks_for(bundle)
    n = len(bundle.frames)
    rgb = {name: np.full((n, 3), np.nan) for name in REGION_NAMES}
    cov = {name: np.zeros(n) for name in REGION_NAMES}
    yaw = np.full(n, np.nan)
    box = np.full((n, 4), np.nan)
    readable = np.zeros(n, dtype=bool)
    hamming = np.full(n, np.nan)
    mad = np.full(n, np.nan)
    prev: tuple[int, np.ndarray] | None = None
    frame_w = 0
    for i, meta in enumerate(bundle.frames):
        img = bundle.read_frame(meta.idx)
        if img is None:
            continue
        readable[i] = True
        h, w = img.shape[:2]
        frame_w = frame_w or w
        rgb_u8 = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        h_now, small = dhash(rgb_u8), rgb_u8[::8, ::8].astype(np.int16)
        if prev is not None and prev[1].shape == small.shape:
            hamming[i] = (h_now ^ prev[0]).bit_count()
            mad[i] = float(np.abs(small - prev[1]).mean())
        prev = (h_now, small)
        found = landmarks.get(meta.idx)
        regions = None
        if found and found.get("landmarks"):
            regions = regions_from_landmarks(to_pixels(found["landmarks"], w, h), w, h)
            yaw[i] = _num(found.get("yaw"))
            box[i] = regions.face_box.clip(w, h).xywh()
        for name, (mean, coverage) in region_means(rgb_u8, regions).items():
            rgb[name][i] = mean
            cov[name][i] = coverage
    t = np.array([f.t_ms for f in bundle.frames], dtype=np.float64)
    series = {name: RegionSeries(rgb_linear=rgb[name], coverage=cov[name]) for name in REGION_NAMES}
    return AnalysisContext(
        bundle=bundle,
        t=t,
        regions=series,
        yaw=yaw,
        face_box=box,
        quality=assess(t, series, box, frame_w, bundle.events, bundle.challenge, thresholds=thresholds),
        thresholds=thresholds,
        readable=readable,
        frame_w=frame_w,
        hamming_prev=hamming,
        mad_prev=mad,
    )
