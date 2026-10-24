"""sensor.cadence and sensor.duplicates (family B, one vote: B.stream). Ported from the old camera_timing and
camera_duplicates checks.

- cadence: frame intervals -> median fps, coefficient of variation, share within +-0.5 ms of the median, longest
  gap. A stall (longest gap over `max_gap_ms`) gives risk 1. "Too perfect" timing gives risk 0.7: a hypothesis that a
  virtual camera delivers frames on a perfect clock. The old repo measured evenness without voting on it because
  hardware-timestamped webcams are very even too, so this cue needs real-webcam numbers at S2.
  Gaps the camera is not to blame for are left out of the timing (issue #33; AGENTS.md rule 3): frames lost in upload
  (the browser numbers every frame it grabs, so `idx` jumps across the gap; integrity.coverage reports them), and a
  gap spanning the scheduled start of a step the client skipped because the page was hidden (no frames arrive while
  a tab is in the background). Only a gap where `idx` stays consecutive is a stall.
- duplicates: a frame is a near-duplicate of the previous readable one when their dHashes differ by <= 2 bits, the
  mean absolute difference on a [::8] pixel grid is < 0.5 (0..255), **and** it is an exact copy or stands out
  against the session's own frame-to-frame change (under `rel_mad`, 0.1, x its median). Relays and virtual cameras
  repeat frames when they cannot keep up; a still person on a camera whose noise the encoder wiped (G11: JPEG
  quality 50) changes little between every pair of frames, which is not repetition.
"""

from __future__ import annotations

import numpy as np

from pulselens.analysis import specs
from pulselens.analysis.context import AnalysisContext
from pulselens.analysis.result import abstain, guarded, result
from pulselens.contracts import CheckResult, ColourStep, Plot, TurnStep

CADENCE, DUPLICATES = specs.SENSOR_CADENCE, specs.SENSOR_DUPLICATES
MAX_PLOT_POINTS = 300


def cadence_features(t: np.ndarray, excluded: np.ndarray | None = None) -> dict[str, float] | None:
    """Interval statistics of frame times (ms), or None with no positive intervals. `excluded` (one per interval,
    len(t) - 1) marks gaps the camera is not to blame for; they are left out and their longest is reported apart."""
    d = np.diff(np.asarray(t, dtype=np.float64))
    out = np.zeros(len(d), dtype=bool) if excluded is None else np.asarray(excluded, dtype=bool)
    ok = np.isfinite(d) & (d > 0)
    kept = d[ok & ~out]
    if not len(kept):
        return None
    median = float(np.median(kept))
    left_out = d[ok & out]
    return {
        "fps": 1000.0 / median,
        "cv": float(np.std(kept) / np.mean(kept)),
        "exact_share": float(np.mean(np.abs(kept - median) <= 0.5)),
        "longest_gap_ms": float(kept.max()),
        "excluded_gaps": float(len(left_out)),
        "longest_excluded_gap_ms": float(left_out.max()) if len(left_out) else 0.0,
    }


def lost_in_upload(idx: np.ndarray) -> np.ndarray:
    """Per interval: the frame numbers jump, so frames between were grabbed but never arrived."""
    return np.diff(np.asarray(idx, dtype=np.int64)) > 1


def hidden_page(t: np.ndarray, ctx: AnalysisContext, slack_ms: float = 250.0) -> np.ndarray:
    """Per interval: the gap spans the scheduled start of a step skipped with "page_hidden". The client checks
    `document.hidden` as each step is due, so the page was hidden then; `slack_ms` covers the scheduling lag."""
    t = np.asarray(t, dtype=np.float64)
    out = np.zeros(max(0, len(t) - 1), dtype=bool)
    ch = ctx.bundle.challenge
    if ch is None or len(t) < 2:
        return out
    steps = {s.step_id: s for s in ch.steps if isinstance(s, ColourStep | TurnStep)}
    for e in ctx.bundle.events:
        step = steps.get(e.step_id)
        if e.status != "skipped" or e.skip_reason != "page_hidden" or step is None:
            continue
        due = ch.baseline_ms + step.start_offset_ms
        out |= (t[:-1] <= due + slack_ms) & (t[1:] >= due - slack_ms)
    return out


def duplicate_runs(dup: np.ndarray) -> int:
    """Length of the longest run of consecutive near-duplicate frames."""
    longest = run_len = 0
    for x in np.asarray(dup, dtype=bool):
        run_len = run_len + 1 if x else 0
        longest = max(longest, run_len)
    return longest


def _cadence_plot(t: np.ndarray) -> Plot:
    d = np.diff(t)
    step = max(1, int(np.ceil(len(d) / MAX_PLOT_POINTS)))
    idx = np.arange(1, len(t))[::step]
    return Plot(kind="cadence", series={"interval_ms": [(float(t[i]), float(t[i] - t[i - 1])) for i in idx]})


def _cadence(ctx: AnalysisContext) -> CheckResult:
    min_frames = int(ctx.thresholds.param(CADENCE.check_id, "min_frames"))
    idx = np.array([m.idx for m in ctx.bundle.frames], dtype=np.int64)
    lost = lost_in_upload(idx) if len(idx) == ctx.n else np.zeros(max(0, ctx.n - 1), dtype=bool)
    hidden = hidden_page(ctx.t, ctx)
    f = cadence_features(ctx.t, lost | hidden) if ctx.n >= min_frames else None
    if f is None:
        return abstain(CADENCE, ["quality.low_fps"],
                       f"Only {ctx.n} frames arrived; at least {min_frames} are needed to judge the frame timing.")
    max_gap = float(ctx.thresholds.param(CADENCE.check_id, "max_gap_ms"))
    f["frames_missing"] = float(np.sum(np.diff(idx)[lost] - 1)) if lost.any() else 0.0
    regular = (f["exact_share"] > float(ctx.thresholds.param(CADENCE.check_id, "too_regular_share"))
               and f["cv"] < float(ctx.thresholds.param(CADENCE.check_id, "too_regular_cv")))
    if f["longest_gap_ms"] > max_gap:
        risk, reasons = 1.0, ["sensor.stall"]
        explanation = (f"The video stopped for {f['longest_gap_ms']:.0f} ms (limit {max_gap:.0f} ms), "
                       "as a stalled software source does.")
    elif regular:
        risk, reasons = 0.7, ["sensor.too_regular"]
        explanation = (f"{f['exact_share']:.0%} of frame intervals were within 0.5 ms of {1000 / f['fps']:.1f} ms "
                       f"(spread {f['cv']:.2%}), a perfect clock; a hypothesis for virtual cameras.")
    else:
        risk, reasons = 0.0, []
        explanation = (f"{f['fps']:.1f} fps with an interval spread of {f['cv']:.1%} and a longest gap of "
                       f"{f['longest_gap_ms']:.0f} ms, consistent with a physical camera.")
    if f["longest_excluded_gap_ms"] > max_gap:  # noted, never scored: the camera is not to blame
        why = []
        if lost.any():
            why.append(f"{f['frames_missing']:.0f} frames lost in upload")
            reasons = [*reasons, "quality.frames_missing"]
        if hidden.any():
            why.append("the page hidden")
            reasons = [*reasons, "quality.page_hidden"]
        explanation += (f" A {f['longest_excluded_gap_ms']:.0f} ms gap is left out of the timing "
                        f"({' and '.join(why)}), not counted as a stall.")
    return result(CADENCE, ctx.thresholds, risk=risk, quality=1.0,
                  features=f, reasons=reasons, explanation=explanation, window_id="all", plot=_cadence_plot(ctx.t))


def _duplicates(ctx: AnalysisContext) -> CheckResult:
    compared = np.isfinite(ctx.mad_prev)
    n_compared = int(compared.sum())
    min_frames = int(ctx.thresholds.param(DUPLICATES.check_id, "min_frames"))
    if n_compared < min_frames:
        return abstain(DUPLICATES, ["quality.low_fps"],
                       f"Only {n_compared} frame pairs could be compared; at least {min_frames} are needed.")
    typical = float(np.median(ctx.mad_prev[compared]))
    with np.errstate(invalid="ignore"):
        rel = float(ctx.thresholds.param(DUPLICATES.check_id, "rel_mad"))
        stands_out = (ctx.mad_prev == 0) | (ctx.mad_prev < rel * typical)
        dup = (compared & (ctx.hamming_prev <= float(ctx.thresholds.param(DUPLICATES.check_id, "max_hamming")))
               & (ctx.mad_prev < float(ctx.thresholds.param(DUPLICATES.check_id, "max_mad"))) & stands_out)
    n_dup = int(dup.sum())
    share = n_dup / n_compared
    max_share = float(ctx.thresholds.param(DUPLICATES.check_id, "max_share"))
    flagged = share >= max_share
    return result(
        DUPLICATES, ctx.thresholds,
        risk=min(1.0, share / max_share),
        quality=float(ctx.readable.mean()),
        features={"dup_share": share, "longest_dup_run": duplicate_runs(dup), "compared": n_compared},
        reasons=["sensor.duplicates"] if flagged else [],
        explanation=f"{n_dup} of {n_compared} frames repeated the one before ({share:.1%}; limit {max_share:.0%}).",
        window_id="all",
    )



@guarded(CADENCE, DUPLICATES)
def run(ctx: AnalysisContext) -> list[CheckResult]:
    return [_cadence(ctx), _duplicates(ctx)]
