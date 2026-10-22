"""White-box tests of the echo onset helper on hand-built series where the right answer is exact (ported)."""

import numpy as np
import pytest

from pulselens.analysis.context import RegionSeries
from pulselens.analysis.echo import BASELINE_MS, WINDOW_MS, chromaticity, direction, echo_onset, response

COLOUR = np.array([0.9, 0.3, 0.4])  # linear RGB of a reddish step
FRAME = 40.0  # ms
PAINTED = 1000.0
ENDED = PAINTED + 400


def onset(t, s, *, painted=PAINTED, ended=ENDED, colour=COLOUR, a_min=0.003):
    return echo_onset(t, s, painted, ended, colour, step_id="c0", region="skin", a_min=a_min)


def series(shift: dict[float, float], *, n: int = 60, coverage: float = 1.0, d: np.ndarray | None = None):
    """Frames every 40 ms from t = 0; chromaticity sits at neutral, moved by `shift[t]` along `d` (default: the step
    colour's direction) from each listed time on, so the projection p(t) equals the shift exactly."""
    t = np.arange(n) * FRAME
    d = direction(COLOUR) if d is None else d
    s = np.zeros(n)
    for start, value in sorted(shift.items()):
        s[t >= start] = value
    rgb = (1.0 / 3.0 + s[:, None] * d[None, :]) * 3.0  # sums to 3; chromaticity = 1/3 + s * d
    return t, RegionSeries(rgb_linear=rgb, coverage=np.full(n, coverage))


def test_chromaticity_sums_to_one_and_is_nan_for_black() -> None:
    x = chromaticity(np.array([[0.2, 0.3, 0.5], [0.0, 0.0, 0.0]]))
    assert x[0] == pytest.approx([0.2, 0.3, 0.5])
    assert np.isnan(x[1]).all()


def test_direction_is_a_unit_vector_that_ignores_brightness() -> None:
    d = direction(COLOUR)
    assert np.linalg.norm(d) == pytest.approx(1.0)
    assert d.sum() == pytest.approx(0.0, abs=1e-12)
    assert direction(COLOUR * 7) == pytest.approx(d)


@pytest.mark.parametrize("colour", [np.array([0.5, 0.5, 0.5]), np.array([0.0, 0.0, 0.0]), np.array([np.nan, 1, 1])])
def test_grey_black_or_nan_colours_have_no_direction(colour) -> None:
    assert direction(colour) is None


def test_onset_is_interpolated_exactly_to_the_threshold_crossing() -> None:
    # Clean baseline (sigma 0), so the threshold is a_min. 1040 ms is at 0.002 and 1080 ms at 0.010: the crossing
    # is 0.001 / 0.008 = 0.125 of the 40 ms between them.
    t, s = series({1040.0: 0.002, 1080.0: 0.010, 1120.0: 0.012})
    o = onset(t, s)
    assert o.valid and o.sigma_pre == 0.0 and o.threshold == 0.003
    assert o.onset_ms == pytest.approx(1040 + 0.125 * 40 - PAINTED)


def test_amplitude_is_the_median_over_the_middle_of_the_step_and_snr_is_in_threshold_units() -> None:
    t, s = series({1080.0: 0.010, 1200.0: 0.020})
    o = onset(t, s)
    assert o.amplitude == pytest.approx(0.020)
    assert o.snr == pytest.approx(0.020 / 0.003)


def test_one_bright_frame_is_not_an_echo() -> None:
    t, s = series({1080.0: 0.05, 1120.0: 0.0})
    o = onset(t, s)
    assert o.valid and o.onset_ms is None


def test_a_change_against_the_step_colour_is_not_an_echo() -> None:
    t, s = series({1080.0: -0.02})
    o = onset(t, s)
    assert o.valid and o.onset_ms is None


def test_a_change_after_the_window_is_not_an_echo() -> None:
    t, s = series({PAINTED + WINDOW_MS + 2 * FRAME: 0.02})
    o = onset(t, s)
    assert o.valid and o.onset_ms is None


def test_noise_in_the_baseline_raises_the_threshold_to_4_sigma() -> None:
    t, s = series({1080.0: 0.02})
    rng = np.random.default_rng(3)
    s = RegionSeries(rgb_linear=s.rgb_linear * (1 + rng.normal(0, 0.004, s.rgb_linear.shape)), coverage=s.coverage)
    o = onset(t, s, a_min=0.0001)
    assert o.threshold == pytest.approx(4 * o.sigma_pre)
    assert o.onset_ms is not None


def test_frames_missing_inside_the_window_are_skipped_not_fatal() -> None:
    t, s = series({1080.0: 0.002, 1160.0: 0.010})
    cov = s.coverage.copy()
    cov[(t > 1100) & (t < 1150)] = 0.0
    o = onset(t, RegionSeries(rgb_linear=s.rgb_linear, coverage=cov))
    assert o.valid and o.onset_ms is not None
    assert 80 <= o.onset_ms <= 160


@pytest.mark.parametrize(
    ("kw", "reason"),
    [
        ({"painted": None}, "no painted time"),
        ({"colour": None}, "no colour direction"),
        ({"colour": np.array([0.4, 0.4, 0.4])}, "no colour direction"),
    ],
)
def test_a_step_without_painted_time_or_colour_is_invalid(kw, reason) -> None:
    t, s = series({1080.0: 0.02})
    o = onset(t, s, **kw)
    assert not o.valid and reason in o.reason


def test_mismatched_or_empty_series_are_invalid() -> None:
    t, s = series({})
    assert onset(np.array([]), RegionSeries(np.empty((0, 3)), np.empty(0))).reason == "no frames"
    assert onset(t[:-1], s).reason == "no frames"


def test_too_few_baseline_frames_is_invalid() -> None:
    t, s = series({})
    o = onset(t, s, painted=BASELINE_MS / 4, ended=BASELINE_MS / 4 + 400)
    assert not o.valid and "baseline" in o.reason


def test_a_region_out_of_view_during_the_step_is_invalid() -> None:
    t, s = series({1080.0: 0.02})
    cov = s.coverage.copy()
    cov[t >= PAINTED] = 0.0
    o = onset(t, RegionSeries(rgb_linear=s.rgb_linear, coverage=cov))
    assert not o.valid and "not visible" in o.reason


def test_response_follows_the_change_in_any_direction() -> None:
    t, s = series({1080.0: 0.02})
    r = response(t, s, PAINTED, ENDED, COLOUR)
    assert r.responded and r.cosine == pytest.approx(1.0) and r.magnitude == pytest.approx(0.02)
    other = np.cross(direction(COLOUR), np.ones(3) / np.sqrt(3))  # in the chromaticity plane, at 90 degrees
    t, s = series({1080.0: 0.02}, d=other / np.linalg.norm(other))
    r = response(t, s, PAINTED, ENDED, COLOUR)
    assert r.responded and r.cosine == pytest.approx(0.0, abs=1e-9)
    t, s = series({})
    assert not response(t, s, PAINTED, ENDED, COLOUR).responded


@pytest.mark.parametrize("seed", range(25))
def test_echo_onset_and_response_never_raise_on_garbage(seed: int) -> None:
    rng = np.random.default_rng(seed)
    n = int(rng.integers(0, 80))
    t = np.sort(rng.uniform(-500, 3000, n))
    rgb = rng.choice([np.nan, np.inf, -1.0, 0.0, 1e9, 0.3], size=(n, 3)) * rng.uniform(0, 1, (n, 3))
    s = RegionSeries(rgb_linear=rgb, coverage=rng.uniform(-1, 2, n))
    painted = float(rng.uniform(-100, 2000))
    o = onset(t, s, painted=painted, ended=painted + 400)
    assert isinstance(o.valid, bool)
    response(t, s, painted, painted + 400, COLOUR)
