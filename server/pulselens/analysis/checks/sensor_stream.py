"""sensor.cadence and sensor.duplicates (family B, one vote: B.stream). Ported from the old camera_timing and
camera_duplicates checks.

- cadence: frame intervals -> median fps, coefficient of variation, share within +-0.5 ms of the median, longest
  gap. A stall (longest gap over `max_gap_ms`) gives risk 1. "Too perfect" timing gives risk 0.7: a hypothesis that a
  virtual camera delivers frames on a perfect clock. The old repo measured evenness without voting on it because
  hardware-timestamped webcams are very even too, so this cue needs real-webcam numbers at S2.
- duplicates: a frame is a near-duplicate of the previous readable one when their dHashes differ by <= 2 bits and
  the mean absolute difference on a [::8] pixel grid is < 0.5 (0..255). Relays and virtual cameras repeat frames when
  they cannot keep up.
"""

from __future__ import annotations

import numpy as np

from pulselens.analysis import specs
from pulselens.analysis.context import AnalysisContext
from pulselens.analysis.result import CheckSpec, abstain, guarded, result
from pulselens.contracts import CheckResult, Plot

CADENCE, DUPLICATES = specs.SENSOR_CADENCE, specs.SENSOR_DUPLICATES
MAX_PLOT_POINTS = 300


def cadence_features(t: np.ndarray) -> dict[str, float] | None:
    """Interval statistics of frame times (ms), or None with no positive intervals."""
    d = np.diff(np.asarray(t, dtype=np.float64))
    d = d[np.isfinite(d) & (d > 0)]
    if not len(d):
        return None
    median = float(np.median(d))
    return {
        "fps": 1000.0 / median,
        "cv": float(np.std(d) / np.mean(d)),
        "exact_share": float(np.mean(np.abs(d - median) <= 0.5)),
        "longest_gap_ms": float(d.max()),
    }


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
    p = ctx.thresholds.params(CADENCE.check_id)
    min_frames = int(p.get("min_frames", 30))
    f = cadence_features(ctx.t) if ctx.n >= min_frames else None
    if f is None:
        return abstain(*_ids(CADENCE), ["quality.low_fps"],
                       f"Only {ctx.n} frames arrived; at least {min_frames} are needed to judge the frame timing.")
    max_gap = float(p.get("max_gap_ms", 1000))
    regular = (f["exact_share"] > float(p.get("too_regular_share", 0.98))
               and f["cv"] < float(p.get("too_regular_cv", 0.01)))
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
    return result(*_ids(CADENCE), risk=risk, flag_at=ctx.thresholds.flag_at(CADENCE.check_id, 0.6), quality=1.0,
                  features=f, reasons=reasons, explanation=explanation,
                  source=ctx.thresholds.source(CADENCE.check_id), window_id="all", plot=_cadence_plot(ctx.t),
                  voting=ctx.thresholds.voting(CADENCE.check_id))


def _duplicates(ctx: AnalysisContext) -> CheckResult:
    p = ctx.thresholds.params(DUPLICATES.check_id)
    compared = np.isfinite(ctx.mad_prev)
    n_compared = int(compared.sum())
    min_frames = int(p.get("min_frames", 30))
    if n_compared < min_frames:
        return abstain(*_ids(DUPLICATES), ["quality.low_fps"],
                       f"Only {n_compared} frame pairs could be compared; at least {min_frames} are needed.")
    with np.errstate(invalid="ignore"):
        dup = (compared & (ctx.hamming_prev <= float(p.get("max_hamming", 2)))
               & (ctx.mad_prev < float(p.get("max_mad", 0.5))))
    n_dup = int(dup.sum())
    share = n_dup / n_compared
    max_share = float(p.get("max_share", 0.05))
    flagged = share >= max_share
    return result(
        *_ids(DUPLICATES),
        risk=min(1.0, share / max_share),
        flag_at=ctx.thresholds.flag_at(DUPLICATES.check_id, 1.0),
        quality=float(ctx.readable.mean()),
        features={"dup_share": share, "longest_dup_run": duplicate_runs(dup), "compared": n_compared},
        reasons=["sensor.duplicates"] if flagged else [],
        explanation=f"{n_dup} of {n_compared} frames repeated the one before ({share:.1%}; limit {max_share:.0%}).",
        source=ctx.thresholds.source(DUPLICATES.check_id),
        window_id="all",
        voting=ctx.thresholds.voting(DUPLICATES.check_id),
    )


def _ids(spec: CheckSpec) -> tuple[str, str, str]:
    return spec.check_id, spec.family, spec.vote_group


@guarded(CADENCE, DUPLICATES)
def run(ctx: AnalysisContext) -> list[CheckResult]:
    return [_cadence(ctx), _duplicates(ctx)]
