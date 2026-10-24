"""The quality gate, service step 3: is each window of the session good enough to judge?

Windows: "baseline" (before the first step), one per shown step ("c0".., "t0", "n0", "d0"..), and "all". Rules
(provisional, in thresholds.yaml under `quality:`): fps, face present, face luma in range, neck visible, face still,
nothing clipped. Every failed rule is a reason code. A window is `usable` when every rule that applies passes; two are
left to the checks: the neck (only checks that use it ask, through `blocking(neck=True)`) and motion in a turn, nod or
digit window (the person is asked to move, so the rule does not apply there and those frames do not count in "all").

Poor quality makes a check abstain; it is never attack evidence (AGENTS.md rule 3).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

from pulselens.analysis import specs
from pulselens.analysis.thresholds import Thresholds
from pulselens.analysis.vision.linearize import linear_to_srgb
from pulselens.contracts import Challenge, ChallengeEvent, ColourStep, DigitStep, NodStep, TurnStep

if TYPE_CHECKING:
    from pulselens.analysis.context import RegionSeries

LUMA = np.array([0.2126, 0.7152, 0.0722])
NEUTRAL_RULES = ("quality.neck_hidden",)  # reported, but blocking only for checks that need the neck


@dataclass
class WindowQuality:
    window_id: str  # "baseline", "c0".."c5", "t0", "all"
    fps: float
    face_present: float  # share of frames with a face
    luma_ok: float  # share of face frames with face mean luma in [40, 220] (sRGB 0..255)
    neck_coverage: float  # median neck coverage over face frames
    motion: float  # median face-box centre speed, face widths per second
    saturated: float  # share of face frames with the face or neck linear mean > 0.95 in any channel
    usable: bool
    reasons: list[str] = field(default_factory=list)

    def blocking(self, *, neck: bool = False) -> list[str]:
        """The reasons that stop a check: all of them, minus the neck unless the check uses it."""
        return [r for r in self.reasons if neck or r not in NEUTRAL_RULES]


@dataclass
class QualityReport:
    windows: dict[str, WindowQuality]

    @property
    def overall(self) -> WindowQuality:
        return self.windows["all"]


def face_luma(rgb_linear: np.ndarray) -> np.ndarray:
    """sRGB luma (0..255) of each frame's mean linear colour."""
    y = np.clip(np.asarray(rgb_linear, dtype=np.float64) @ LUMA, 0, 1)
    return linear_to_srgb(y) * 255.0


def _fps(t: np.ndarray) -> float:
    d = np.diff(t)
    d = d[np.isfinite(d) & (d > 0)]
    return 1000.0 / float(np.median(d)) if len(d) else 0.0


def _motion(t: np.ndarray, box: np.ndarray) -> float:
    """Median speed of the face-box centre between consecutive face frames, in face widths per second."""
    face = np.isfinite(box).all(axis=1)
    if face.sum() < 2:
        return 0.0
    tt, b = t[face], box[face]
    centre = b[:, :2] + b[:, 2:] / 2
    dt = np.diff(tt)
    width = (b[1:, 2] + b[:-1, 2]) / 2
    ok = (dt > 0) & (width > 0)
    if not ok.any():
        return 0.0
    speed = np.linalg.norm(np.diff(centre, axis=0), axis=1)[ok] / width[ok] / dt[ok] * 1000.0
    return float(np.median(speed))


def _window(window_id: str, mask: np.ndarray, t: np.ndarray, regions: Mapping[str, RegionSeries],
            face_box: np.ndarray, th: Thresholds, *, motion_rule: bool) -> WindowQuality:
    n = int(mask.sum())
    tt, box = t[mask], face_box[mask]
    face = np.isfinite(box).all(axis=1) if n else np.zeros(0, dtype=bool)
    skin = regions["skin"].rgb_linear[mask][face] if n else np.empty((0, 3))
    neck = regions["neck"] if "neck" in regions else None
    lo, hi = (float(x) for x in th.param("quality", "luma"))
    luma = face_luma(skin) if len(skin) else np.empty(0)
    luma_ok = float(np.mean((luma >= lo) & (luma <= hi))) if len(luma) else 0.0
    neck_cov = float(np.median(neck.coverage[mask][face])) if neck is not None and face.any() else 0.0
    sat_level = float(th.param("quality", "saturation"))
    clipped = np.zeros(int(face.sum()), dtype=bool)
    if face.any():
        with np.errstate(invalid="ignore"):
            clipped = (skin > sat_level).any(axis=1)
            if neck is not None:
                clipped |= (neck.rgb_linear[mask][face] > sat_level).any(axis=1)
    w = WindowQuality(
        window_id=window_id,
        fps=_fps(tt) if n >= 2 else 0.0,
        face_present=float(face.mean()) if n else 0.0,
        luma_ok=luma_ok,
        neck_coverage=neck_cov,
        motion=_motion(tt, box) if n else 0.0,
        saturated=float(clipped.mean()) if len(clipped) else 0.0,
        usable=False,
    )
    reasons = []
    if w.fps < float(th.param("quality", "min_fps")):
        reasons.append("quality.low_fps")
    min_present = float(th.param("quality", "min_face_present"))
    if w.face_present < min_present:
        reasons.append("quality.no_face")
    elif w.luma_ok < float(th.param("quality", "min_luma_ok")):
        reasons.append("quality.too_dark" if float(np.median(luma)) < (lo + hi) / 2 else "quality.too_bright")
    if w.face_present >= min_present and w.neck_coverage < float(th.param("quality", "min_neck_coverage")):
        reasons.append("quality.neck_hidden")
    if motion_rule and w.motion > float(th.param("quality", "max_motion")):
        reasons.append("quality.moving")
    if w.saturated > float(th.param("quality", "max_saturated")):
        reasons.append("quality.clipped")
    w.reasons = reasons
    w.usable = not w.blocking()
    return w


def assess(t: np.ndarray, regions: Mapping[str, RegionSeries], face_box: np.ndarray, events: list[ChallengeEvent],
           challenge: Challenge | None, *, thresholds: Thresholds | None = None) -> QualityReport:
    """Motion is measured in face widths, so no pixel size is needed."""
    th = thresholds or Thresholds.load()
    t = np.asarray(t, dtype=np.float64)
    shown = {e.step_id: e for e in events if e.status == "shown" and e.painted_t_ms is not None}
    windows: dict[str, WindowQuality] = {}
    turn = np.zeros(len(t), dtype=bool)
    if challenge is not None:
        windows["baseline"] = _window("baseline", t < challenge.baseline_ms, t, regions, face_box, th,
                                      motion_rule=True)
        for step in challenge.steps:
            e = shown.get(step.step_id)
            if e is None:
                continue
            if isinstance(step, ColourStep):
                end = e.ended_t_ms if e.ended_t_ms is not None else e.painted_t_ms + step.dwell_ms
                mask = (t >= e.painted_t_ms) & (t <= end)
                windows[step.step_id] = _window(step.step_id, mask, t, regions, face_box, th, motion_rule=True)
            elif isinstance(step, TurnStep):
                ended = e.ended_t_ms if e.ended_t_ms is not None else e.painted_t_ms + step.duration_ms
                end = ended + float(th.param(specs.TURN_FOLLOW.check_id, "tail_ms"))
                mask = (t >= e.painted_t_ms) & (t <= end)
                turn |= mask
                windows[step.step_id] = _window(step.step_id, mask, t, regions, face_box, th, motion_rule=False)
            elif isinstance(step, NodStep | DigitStep):  # asked to nod or to speak: like the turn, motion is no rule
                tail = float(th.param(specs.TURN_NOD.check_id, "tail_ms")) if isinstance(step, NodStep) else 0.0
                end = (e.ended_t_ms if e.ended_t_ms is not None else e.painted_t_ms + step.duration_ms) + tail
                mask = (t >= e.painted_t_ms) & (t <= end)
                turn |= mask
                windows[step.step_id] = _window(step.step_id, mask, t, regions, face_box, th, motion_rule=False)
    windows["all"] = _window("all", np.ones(len(t), dtype=bool), t, regions, face_box, th, motion_rule=False)
    if (~turn).sum() >= 2:  # motion over the whole session, without the frames where the person was asked to turn
        still = _window("all", ~turn, t, regions, face_box, th, motion_rule=True)
        windows["all"].motion = still.motion
        if "quality.moving" in still.reasons:
            windows["all"].reasons.append("quality.moving")
            windows["all"].usable = False
    return QualityReport(windows=windows)
