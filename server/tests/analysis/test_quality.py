from pathlib import Path

import numpy as np
import pytest

from pulselens.analysis.checks.light_response import run as light_response
from pulselens.analysis.context import RegionSeries, build_context
from pulselens.analysis.quality import assess, face_luma
from pulselens.analysis.thresholds import Thresholds
from pulselens.analysis.vision.linearize import srgb_to_linear
from pulselens.bundle import load_bundle
from pulselens.contracts import Challenge, ChallengeEvent, ColourStep, TurnStep
from tests.fixtures.synth import make_session

W = 320
THRESHOLDS = Thresholds.load()


def _linear_for_luma(luma: float) -> np.ndarray:
    """A grey whose sRGB luma (0..255) is `luma`."""
    return np.full(3, float(srgb_to_linear(np.array([luma / 255.0]))[0]))


def _challenge() -> tuple[Challenge, list[ChallengeEvent]]:
    ch = Challenge(session_id="s", nonce="n", mode="CAPABLE", baseline_ms=1500, total_ms=6000, steps=[
        ColourStep(step_id="c0", hue_deg=40, start_offset_ms=0, dwell_ms=400),
        ColourStep(step_id="c1", hue_deg=200, start_offset_ms=1000, dwell_ms=400),
        TurnStep(step_id="t0", direction="left", start_offset_ms=2400, duration_ms=3000),
    ])
    events = [
        ChallengeEvent(step_id="c0", status="shown", painted_t_ms=1516, ended_t_ms=1916, shown_rgb=(0.8, 0.7, 0.4)),
        ChallengeEvent(step_id="c1", status="shown", painted_t_ms=2516, ended_t_ms=2916, shown_rgb=(0.4, 0.8, 0.8)),
        ChallengeEvent(step_id="t0", status="shown", painted_t_ms=3916, ended_t_ms=6916, shown_rgb=None),
    ]
    return ch, events


def _session(*, fps: float = 30.0, luma: float = 120.0, neck_coverage: float = 1.0, face: float = 1.0,
             speed: float = 0.0, speed_in: str = "all", saturate: float = 0.0, end_ms: float = 7500.0):
    """Arrays for assess(): a still face box 80 px wide, `speed` face widths per second when moving."""
    t = np.arange(0, end_ms, 1000 / fps)
    n = len(t)
    skin = np.tile(_linear_for_luma(luma), (n, 1))
    skin[: int(saturate * n)] = 0.97
    regions = {
        "skin": RegionSeries(skin, np.ones(n)),
        "neck": RegionSeries(np.tile(_linear_for_luma(100), (n, 1)), np.full(n, neck_coverage)),
    }
    box = np.tile([120.0, 40.0, 80.0, 110.0], (n, 1))
    ch, events = _challenge()
    moving = np.ones(n, dtype=bool) if speed_in == "all" else (t >= 3916) & (t <= 6916)
    x = np.cumsum(np.r_[0, np.diff(t)] * moving) / 1000 * speed * 80
    box[:, 0] += x
    absent = np.arange(n) >= int(face * n)
    box[absent] = np.nan
    for r in regions.values():
        r.rgb_linear[absent] = np.nan
        r.coverage[absent] = 0.0
    return dict(t=t, regions=regions, face_box=box, frame_w=W, events=events, challenge=ch)


def test_a_clean_session_is_usable_in_every_window() -> None:
    q = assess(**_session(), thresholds=THRESHOLDS)
    assert set(q.windows) == {"baseline", "c0", "c1", "t0", "all"}
    assert q.overall is q.windows["all"]
    for w in q.windows.values():
        assert w.usable and w.reasons == [], (w.window_id, w.reasons)
    assert q.overall.fps == pytest.approx(30, abs=0.5)
    assert q.overall.face_present == 1 and q.overall.luma_ok == 1 and q.overall.neck_coverage == 1


@pytest.mark.parametrize(
    ("kw", "reason"),
    [
        ({"fps": 10}, "quality.low_fps"),
        ({"face": 0.5}, "quality.no_face"),
        ({"luma": 30}, "quality.too_dark"),
        ({"luma": 240}, "quality.too_bright"),
        ({"neck_coverage": 0.3}, "quality.neck_hidden"),
        ({"speed": 1.0}, "quality.moving"),
        ({"saturate": 0.5}, "quality.clipped"),
    ],
)
def test_one_reason_per_rule(kw: dict, reason: str) -> None:
    w = assess(**_session(**kw), thresholds=THRESHOLDS).overall
    assert reason in w.reasons, w
    if reason == "quality.neck_hidden":
        assert w.usable  # the neck matters only to checks that use it
        assert reason in w.blocking(neck=True) and reason not in w.blocking()
    else:
        assert not w.usable and reason in w.blocking()


def test_the_turn_window_ignores_motion() -> None:
    q = assess(**_session(speed=1.0, speed_in="turn"), thresholds=THRESHOLDS)
    assert q.windows["t0"].motion > 0.5
    assert q.windows["t0"].usable and "quality.moving" not in q.windows["t0"].reasons
    assert q.overall.usable  # the turn's own movement does not count against the whole session
    assert q.windows["c0"].usable


def test_motion_is_in_face_widths_per_second() -> None:
    q = assess(**_session(speed=0.3), thresholds=THRESHOLDS)
    assert q.overall.motion == pytest.approx(0.3, rel=0.05)


def test_an_empty_window_is_not_usable() -> None:
    q = assess(**_session(end_ms=1000), thresholds=THRESHOLDS)  # frames end before the first step
    assert not q.windows["c0"].usable and "quality.low_fps" in q.windows["c0"].reasons
    assert q.windows["c0"].fps == 0


def test_no_frames_at_all_does_not_raise() -> None:
    s = _session()
    s.update(t=np.empty(0), face_box=np.empty((0, 4)),
             regions={k: RegionSeries(np.empty((0, 3)), np.empty(0)) for k in ("skin", "neck")})
    assert not assess(**s, thresholds=THRESHOLDS).overall.usable


def test_face_luma_is_the_srgb_luma_of_the_linear_mean() -> None:
    assert face_luma(np.array([_linear_for_luma(120.0)]))[0] == pytest.approx(120, abs=0.01)


# --- wired into the context and light.response ------------------------------------------------------------------


@pytest.fixture(scope="module")
def genuine_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return make_session(tmp_path_factory.mktemp("q"), kind="genuine")


def test_build_context_fills_the_quality_report(genuine_path: Path) -> None:
    ctx = build_context(load_bundle(genuine_path), THRESHOLDS)
    assert set(ctx.quality.windows) == {"baseline", *(f"c{k}" for k in range(6)), "t0", "all"}
    assert all(w.usable for w in ctx.quality.windows.values())


def _requalify(ctx) -> None:
    ctx.quality = assess(ctx.t, ctx.regions, ctx.face_box, ctx.frame_w, ctx.bundle.events, ctx.bundle.challenge,
                         thresholds=ctx.thresholds)


def test_light_response_abstains_with_the_window_reasons_when_too_dark(genuine_path: Path) -> None:
    ctx = build_context(load_bundle(genuine_path), THRESHOLDS)
    for r in ctx.regions.values():
        r.rgb_linear *= 0.02  # chromaticity (and so the echo) is unchanged; only the brightness
    _requalify(ctx)
    [r] = light_response(ctx)
    assert r.status == "abstain" and not r.flag
    assert "light.too_few_steps" in r.reason_codes and "quality.too_dark" in r.reason_codes


def test_a_step_where_the_face_moved_is_left_out(genuine_path: Path) -> None:
    ctx = build_context(load_bundle(genuine_path), THRESHOLDS)
    c0 = next(e for e in ctx.bundle.events if e.step_id == "c0")
    during = (ctx.t >= c0.painted_t_ms) & (ctx.t <= c0.ended_t_ms)
    ctx.face_box[during, 0] += np.arange(during.sum()) * 20.0  # 20 px a frame: fast sideways movement
    _requalify(ctx)
    assert "quality.moving" in ctx.quality.windows["c0"].reasons
    [r] = light_response(ctx)
    assert r.status == "usable" and not r.flag and r.features["steps_valid"] == 5
