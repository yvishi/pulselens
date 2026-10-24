"""pulse.coherence (family A, A.pulse): does the face's pulse match the neck's? Logged only (G10).

Experimental and never in the decision: `flag` is always false (specs.PULSE_COHERENCE.never_flags, `voting: false`).
A swapped face can carry the driver's real pulse (Seibold 2025), so a matching pulse proves little; it is recorded to
measure at S2 whether a mismatch separates attacks at all.

Frames used: face and neck seen, the face box still (centre speed under quality.max_motion face widths per second),
and outside each colour step and `light_tail_ms` after it (the screen's light is not a pulse). The frames are resampled
evenly at the session's fps; a gap of up to `max_fill_ms` is bridged by linear interpolation, a longer one ends the
span, and the longest span is used. It needs `min_seconds`, at `min_fps` or more, in a session the quality gate passed
(face, light, neck). The skin region (forehead and both cheeks, pooled) is the face. vision/pulse.py: POS, then the
face's pulse SNR and the face-neck coherence at the face's peak.

risk = 1 - coherence. Never stored or plotted: the waveform, the peak frequency, a heart rate (`plot` stays None).
"""

from __future__ import annotations

import numpy as np

from pulselens.analysis import specs
from pulselens.analysis.context import AnalysisContext
from pulselens.analysis.result import abstain, guarded, result
from pulselens.analysis.vision.pulse import SEGMENT_S, pos, snr_and_coherence
from pulselens.contracts import CheckResult, ColourStep

SPEC = specs.PULSE_COHERENCE
CAVEAT = "Experimental, not used in the decision; swaps can carry the driver's real pulse (Seibold 2025)."


def _still(t: np.ndarray, box: np.ndarray, max_motion: float) -> np.ndarray:
    """Per frame: the face-box centre moved under `max_motion` face widths per second since the previous frame."""
    centre = box[:, :2] + box[:, 2:] / 2
    with np.errstate(invalid="ignore", divide="ignore"):
        speed = np.linalg.norm(np.diff(centre, axis=0), axis=1) / box[1:, 2] / np.diff(t) * 1000.0
    still = np.ones(len(t), dtype=bool)
    still[1:] = ~(speed >= max_motion)  # NaN (a frame without a face either side) is judged by `seen`, not here
    return still


def _span(t: np.ndarray, good: np.ndarray, fs: float, max_fill: float) -> np.ndarray:
    """The longest evenly spaced grid (ms) whose gaps between good frames are all at most `max_fill`."""
    tg = t[good]
    best = np.empty(0)
    if len(tg) < 2:
        return best
    breaks = np.flatnonzero(np.diff(tg) > max_fill)
    for a, b in zip(np.r_[0, breaks + 1], np.r_[breaks, len(tg) - 1], strict=True):
        grid = np.arange(tg[a], tg[b], 1000.0 / fs)
        if len(grid) > len(best):
            best = grid
    return best


@guarded(SPEC)
def run(ctx: AnalysisContext) -> list[CheckResult]:
    th = lambda key: float(ctx.thresholds.param(SPEC.check_id, key))  # noqa: E731
    overall = ctx.quality.overall
    min_fps = th("min_fps")
    if overall.fps < min_fps:
        return [abstain(SPEC, ["pulse.not_measured", "quality.low_fps"], f"The camera delivered {overall.fps:.1f} fps, "
                        f"below the {min_fps:.0f} fps a pulse needs. {CAVEAT}", features={"fps": overall.fps},
                        window_id="all")]
    blocking = [r for r in overall.blocking(neck=True) if r != "quality.moving"]  # moving frames are left out below
    if blocking:
        return [abstain(SPEC, ["pulse.not_measured", *blocking], f"Pulse coherence needs a clear, well-lit face and "
                        f"neck. {CAVEAT}", window_id="all")]

    t = ctx.t
    face, neck = ctx.regions["skin"].rgb_linear, ctx.regions["neck"].rgb_linear
    seen = np.isfinite(face).all(axis=1) & np.isfinite(neck).all(axis=1) & np.isfinite(ctx.face_box).all(axis=1)
    lit = np.zeros(len(t), dtype=bool)
    ch = ctx.bundle.challenge
    steps = {s.step_id: s for s in ch.steps if isinstance(s, ColourStep)} if ch is not None else {}
    for e in ctx.bundle.events:
        if e.step_id in steps and e.status == "shown" and e.painted_t_ms is not None:
            end = e.ended_t_ms if e.ended_t_ms is not None else e.painted_t_ms + steps[e.step_id].dwell_ms
            lit |= (t >= e.painted_t_ms) & (t <= end + th("light_tail_ms"))
    good = seen & ~lit & _still(t, ctx.face_box, float(ctx.thresholds.param("quality", "max_motion")))
    fs = float(round(overall.fps))
    grid = _span(t, good, fs, th("max_fill_ms"))
    seconds = len(grid) / fs
    if seconds < max(th("min_seconds"), SEGMENT_S):
        return [abstain(SPEC, ["pulse.not_measured"], f"Only {seconds:.1f} s of steady video without the screen's "
                        f"colours (need {th('min_seconds'):.0f} s). {CAVEAT}",
                        features={"seconds": seconds}, window_id="all")]

    tg = t[good]
    inside = (tg >= grid[0]) & (tg <= grid[-1])
    clean_share = float(inside.sum() / len(grid))
    face_g = np.column_stack([np.interp(grid, tg, face[good][:, c]) for c in range(3)])
    neck_g = np.column_stack([np.interp(grid, tg, neck[good][:, c]) for c in range(3)])
    if min(float(np.std(face_g[:, 1] / face_g[:, 1].mean())), float(np.std(neck_g[:, 1] / neck_g[:, 1].mean()))) < 1e-4:
        return [abstain(SPEC, ["pulse.not_measured"], f"The face or neck did not change at all over {seconds:.0f} s "
                        f"(identical frames), so there is no pulse to compare. {CAVEAT}",
                        features={"seconds": seconds}, window_id="all")]
    snr, coherence = snr_and_coherence(pos(face_g, fs), pos(neck_g, fs), fs)
    features = {"snr_face": snr, "coherence_face_neck": coherence, "seconds": seconds,
                "clean_share": min(1.0, clean_share)}
    return [result(SPEC, ctx.thresholds, risk=1.0 - coherence, quality=min(1.0, clean_share), features=features,
                   reasons=[], explanation=f"Face pulse SNR {snr:.1f} dB; face-neck pulse coherence {coherence:.2f} "
                   f"over {seconds:.0f} s. {CAVEAT}", window_id="all")]
