"""Echo onset: how a region's colour answers one painted colour step. Ported from the old repo's echo.py; the input is
now a step's painted/ended times and linear colour instead of the old Pulse.

1. Chromaticity x = RGB / sum(RGB) of the region's mean linear colour.
2. Expected direction d = the step colour's chromaticity minus neutral (1/3, 1/3, 1/3), as a unit vector.
3. Projection p(t) = (x(t) - mean of x over the 300 ms before `painted`) . d.
4. Onset = the first two consecutive frames above max(4 sigma_pre, a_min) within 700 ms of `painted`,
   interpolated linearly to the threshold crossing. An echo whose hold amplitude stays below the threshold is noise
   that happened to cross twice, not an echo.
5. Constant-fraction onset = the same rising edge timed where it reaches half of its own hold amplitude. A fixed
   threshold is crossed later on a weak echo than on a strong one, by up to a frame; half-height is not.

`response` is separate from the onset: the mean chromaticity change over the step, in any direction, so a face that
answers with the wrong colour is told apart from a face that does not answer at all.

Pure: frame times, one region's series and one step in; dataclasses out. Never raises on bad data.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from pulselens.analysis.context import RegionSeries

BASELINE_MS = 300.0
WINDOW_MS = 700.0
K_SIGMA = 4.0
MIN_BASELINE_FRAMES = 3
MIN_COVERAGE = 0.5  # a frame counts for a region when at least this much of it is in view
MIN_WINDOW_SHARE = 0.8  # share of the window's frames that must be usable
RESPONSE_FROM_MS = 200.0  # the response window: from 200 ms after painted to 100 ms after the step ends
RESPONSE_AFTER_END_MS = 100.0


@dataclass
class EchoOnset:
    step_id: str
    region: str
    valid: bool  # enough clean frames to judge; an invalid step is left out, not counted as "no echo"
    onset_ms: float | None = None  # after `painted`; None = no echo
    onset_cf_ms: float | None = None  # constant-fraction onset (half of `amplitude`), after `painted`
    amplitude: float | None = None  # projection held during the step
    peak: float | None = None  # highest projection within the window, echo or not
    threshold: float | None = None
    sigma_pre: float | None = None
    reason: str | None = None
    t_rel: np.ndarray = field(default_factory=lambda: np.empty(0))  # for plots: time after painted, ms
    p: np.ndarray = field(default_factory=lambda: np.empty(0))  # for plots: projection

    @property
    def snr(self) -> float | None:
        """Hold amplitude in units of the onset threshold (>= 1 for every echo)."""
        if self.amplitude is None or not self.threshold:
            return None
        return self.amplitude / self.threshold


@dataclass
class Response:
    """The chromaticity change over a step, in any direction."""

    magnitude: float  # |mean x over the response window - baseline mean|
    cosine: float | None  # with the expected direction; None without a change
    threshold: float  # max(4 sigma of the baseline's distance from its mean, a_min)

    @property
    def responded(self) -> bool:
        return self.magnitude > self.threshold


def chromaticity(rgb: np.ndarray) -> np.ndarray:
    rgb = np.asarray(rgb, dtype=np.float64)
    s = rgb.sum(axis=-1, keepdims=True)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(s > 0, rgb / s, np.nan)


def direction(colour: np.ndarray | None) -> np.ndarray | None:
    if colour is None:
        return None
    d = chromaticity(np.asarray(colour, dtype=np.float64)) - 1.0 / 3.0
    n = float(np.linalg.norm(d))
    return d / n if np.isfinite(n) and n > 1e-6 else None


def _usable(series: RegionSeries) -> tuple[np.ndarray, np.ndarray]:
    x = chromaticity(series.rgb_linear)
    with np.errstate(invalid="ignore"):
        usable = (np.asarray(series.coverage) >= MIN_COVERAGE) & np.isfinite(x).all(axis=1)
    return x, usable


def echo_onset(
    t: np.ndarray,
    series: RegionSeries,
    painted: float | None,
    ended: float | None,
    colour: np.ndarray | None,
    *,
    step_id: str = "",
    region: str = "",
    a_min: float = 0.003,
) -> EchoOnset:
    """`colour` is the step's linear RGB as painted."""
    out = EchoOnset(step_id=step_id, region=region, valid=False)
    d = direction(colour)
    if painted is None or not np.isfinite(painted) or d is None:
        out.reason = "no painted time or no colour direction"
        return out
    t = np.asarray(t, dtype=np.float64)
    if len(t) == 0 or len(series.rgb_linear) != len(t) or len(series.coverage) != len(t):
        out.reason = "no frames"
        return out
    duration = (ended - painted) if ended is not None and np.isfinite(ended) and ended > painted else 400.0
    x, usable = _usable(series)

    base = usable & (t >= painted - BASELINE_MS) & (t < painted)
    if base.sum() < MIN_BASELINE_FRAMES:
        out.reason = f"{int(base.sum())} usable baseline frames"
        return out
    in_window = (t >= painted) & (t <= painted + WINDOW_MS)
    if not in_window.any() or usable[in_window].mean() < MIN_WINDOW_SHARE:
        out.reason = "region not visible during the step"
        return out

    with np.errstate(invalid="ignore", over="ignore"):
        p = (x - x[base].mean(axis=0)) @ d
    sigma = float(np.std(p[base], ddof=1))
    if not np.isfinite(sigma):
        out.reason = "baseline not finite"
        return out
    thr = max(K_SIGMA * sigma, a_min)
    span = usable & (t >= painted - BASELINE_MS) & (t <= painted + WINDOW_MS + duration)
    out.valid, out.threshold, out.sigma_pre = True, thr, sigma
    out.t_rel, out.p = t[span] - painted, p[span]

    idx = np.flatnonzero(usable & in_window)
    out.peak = float(p[idx].max()) if len(idx) else None
    for a, b in zip(idx[:-1], idx[1:], strict=False):
        if p[a] > thr and p[b] > thr:
            t_cross = _crossing(t, p, usable, a, thr)
            hold = usable & (t >= t_cross + 0.25 * duration) & (t <= t_cross + 0.75 * duration)
            amplitude = float(np.median(p[hold])) if hold.any() else float(p[a : b + 1].max())
            if amplitude <= thr:
                continue
            out.onset_ms = float(t_cross - painted)
            out.amplitude = amplitude
            half = 0.5 * amplitude
            first = next((j for j in idx if j >= a and p[j] >= half), b)
            out.onset_cf_ms = float(_crossing(t, p, usable, first, half) - painted)
            break
    return out


def response(
    t: np.ndarray, series: RegionSeries, painted: float, ended: float, colour: np.ndarray | None, *,
    a_min: float = 0.003,
) -> Response | None:
    """The mean chromaticity change from the 300 ms baseline to [painted + 200, ended + 100] ms; None without enough
    usable frames on either side."""
    t = np.asarray(t, dtype=np.float64)
    x, usable = _usable(series)
    base = usable & (t >= painted - BASELINE_MS) & (t < painted)
    win = usable & (t >= painted + RESPONSE_FROM_MS) & (t <= ended + RESPONSE_AFTER_END_MS)
    if base.sum() < MIN_BASELINE_FRAMES or win.sum() < 2:
        return None
    mean = x[base].mean(axis=0)
    delta = x[win].mean(axis=0) - mean
    spread = np.linalg.norm(x[base] - mean, axis=1)
    thr = max(K_SIGMA * float(np.sqrt(np.mean(spread**2))), a_min)
    magnitude = float(np.linalg.norm(delta))
    d = direction(colour)
    cosine = float(delta @ d / magnitude) if d is not None and magnitude > 0 else None
    return Response(magnitude=magnitude, cosine=cosine, threshold=thr)


def _crossing(t: np.ndarray, p: np.ndarray, usable: np.ndarray, j: int, level: float) -> float:
    """Time where p rises through `level` just before frame j: interpolated from the last usable frame before j."""
    prev = np.flatnonzero(usable[:j])
    if len(prev) and p[prev[-1]] < level:
        k = prev[-1]
        return float(t[k] + (level - p[k]) / (p[j] - p[k]) * (t[j] - t[k]))
    return float(t[j])
