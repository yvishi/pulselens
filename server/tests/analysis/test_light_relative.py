"""light.face_neck and light.background: family C, one vote together (C.relative)."""

from pathlib import Path

import pytest

from pulselens.analysis import analyze
from pulselens.analysis.checks import light_background, light_face_neck
from pulselens.analysis.context import AnalysisContext, build_context
from pulselens.analysis.thresholds import PROVISIONAL, Thresholds, _read
from pulselens.bundle import load_bundle
from tests.analysis.conftest import requalify
from tests.fixtures.synth import H


def _ctx(path: Path) -> AnalysisContext:
    return build_context(load_bundle(path), Thresholds.load())


def _one(check, ctx: AnalysisContext, check_id: str):
    results = check.run(ctx)
    assert len(results) == 1
    r = results[0]
    assert r.check_id == check_id and r.family == "C" and r.vote_group == "C.relative" and r.window_id == "all"
    return r


def face_neck(ctx):
    return _one(light_face_neck, ctx, "light.face_neck")


def background(ctx):
    return _one(light_background, ctx, "light.background")


@pytest.fixture
def genuine(synth) -> AnalysisContext:
    return synth.context(kind="genuine", turn=None)


# --- light.face_neck ---------------------------------------------------------------------------------------------


def test_genuine_face_and_neck_answer_together(genuine: AnalysisContext) -> None:
    r = face_neck(genuine)
    assert r.status == "usable" and not r.flag, r.explanation
    assert r.features["pairs"] == 6 and r.features["neck_only_steps"] == 0
    assert r.features["median_ratio"] == pytest.approx(0.9, abs=0.2)
    assert "median_cf_delta_ms" in r.features  # measured, not scored
    assert "hypothesis" in r.explanation


@pytest.mark.parametrize("gain", [0.3, 3.0])
def test_a_shirt_that_answers_weaker_or_stronger_is_not_flagged(synth, gain: float) -> None:
    r = face_neck(synth.context(kind="genuine", turn=None, neck_gain=gain))
    assert r.status == "usable" and not r.flag, r.explanation


def test_a_neck_that_answers_while_the_face_does_not_is_flagged(synth) -> None:
    r = face_neck(synth.context(kind="swap_no_face_echo", turn=None))
    assert r.flag and r.risk == 1.0 and "light.neck_only" in r.reason_codes
    # >= 5: a face noise frame that peaks over its threshold makes that step unclear, not silent (ported rule)
    assert r.features["neck_only_steps"] >= 5
    assert "neck" in r.explanation and "face" in r.explanation


def test_a_face_echo_far_outside_the_neck_ratio_is_flagged(synth) -> None:
    # The neck must still answer clearly (>= 2x its threshold), so a very weak neck needs quiet frames to be compared.
    ctx = synth.context(kind="genuine", turn=None, neck_gain=0.08, noise=0.001)
    r = face_neck(ctx)
    assert r.features["median_ratio"] > 5.66 and not r.flag  # 6.2x: inside ln 8, where real shirts reach (S2)
    full = _read(PROVISIONAL)
    ctx.thresholds = Thresholds({**full, "light.face_neck": {**full["light.face_neck"], "ratio_log_tolerance": 1.386}})
    r = face_neck(ctx)
    assert r.flag and "light.ratio" in r.reason_codes  # the rule itself: beyond ln 4 + half of ln 2


def test_a_neck_too_weak_to_compare_abstains(synth) -> None:
    r = face_neck(synth.context(kind="genuine", turn=None, neck_gain=0.1))
    assert r.status == "abstain" and not r.flag and "light.weak_echoes" in r.reason_codes


def test_a_noisy_face_is_unclear_not_silent(synth) -> None:
    # The old repo's fix: a face whose threshold is too high to hear a quarter of the neck's echo is not "silent".
    r = face_neck(synth.context(kind="swap_no_face_echo", turn=None, face_noise_gain=15))
    assert not r.flag and r.status == "abstain", r.explanation
    assert r.features["neck_only_steps"] == 0 and r.features["unclear_steps"] >= 4


def test_a_neck_half_out_of_frame_abstains(synth) -> None:
    chin_y = H - 5.5 - 0.4 * 44  # 40% of the 44 px nominal neck box inside the frame
    r = face_neck(synth.context(kind="genuine", turn=None, chin_y=chin_y))
    assert r.status == "abstain" and "quality.neck_hidden" in r.reason_codes and not r.flag


def test_a_saturated_neck_abstains(genuine: AnalysisContext) -> None:
    ctx = genuine
    ctx.regions["neck"].rgb_linear[:] = 0.99
    requalify(ctx)
    r = face_neck(ctx)
    assert r.status == "abstain" and "quality.clipped" in r.reason_codes


def test_no_echo_on_either_side_abstains(synth) -> None:
    r = face_neck(synth.context(kind="replay", turn=None))
    assert r.status == "abstain" and "light.too_few_steps" in r.reason_codes and not r.flag


# --- light.background ---------------------------------------------------------------------------------------------


def test_genuine_background_answers_much_less_than_the_face(genuine: AnalysisContext) -> None:
    r = background(genuine)
    assert r.status == "usable" and not r.flag, r.explanation
    assert r.features["median_bg_ratio"] < 0.2
    assert "hypothesis" in r.explanation


def test_a_background_that_answers_like_the_face_is_flagged(synth) -> None:
    r = background(synth.context(kind="genuine", turn=None, background_echo=1.0))
    assert r.flag and "light.background_even" in r.reason_codes
    assert r.features["median_bg_ratio"] > 0.8


def test_a_weak_face_echo_abstains(synth) -> None:
    r = background(synth.context(kind="replay", turn=None))
    assert r.status == "abstain" and "light.weak_face_echo" in r.reason_codes and not r.flag


def test_too_little_background_abstains(genuine: AnalysisContext) -> None:
    ctx = genuine
    ctx.regions["background"].coverage[:] = 0.05
    r = background(ctx)
    assert r.status == "abstain" and not r.flag


# --- both ---------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("check", [light_face_neck, light_background])
def test_light_not_in_the_plan_is_not_run(synth, check) -> None:
    assert check.run(synth.context(kind="genuine", n_colour=0)) == []


@pytest.mark.parametrize("check", [light_face_neck, light_background])
def test_10_fps_abstains(synth, check) -> None:
    [r] = check.run(synth.context(kind="genuine", turn=None, fps=10))
    assert r.status == "abstain" and "quality.low_fps" in r.reason_codes


@pytest.mark.parametrize("kind", ["genuine", "replay"])
@pytest.mark.parametrize("noise", [0.06, 0.1])
def test_heavy_noise_is_never_a_flag(synth, kind: str, noise: float) -> None:
    ctx = synth.context(kind=kind, turn=None, noise=noise, seed=3)
    for check in (light_face_neck, light_background):
        for r in check.run(ctx):
            assert not r.flag, (r.check_id, r.explanation)


def test_analyze_includes_both(synth) -> None:
    ids = {r.check_id for r in analyze(synth.session(kind="genuine", turn=None))}
    assert {"light.face_neck", "light.background"} <= ids


@pytest.mark.parametrize("noise", [0.003, 0.006])
@pytest.mark.parametrize("seed", [0, 1, 2])
def test_a_faint_face_beside_a_strong_shirt_is_not_neck_only(synth, noise: float, seed: int) -> None:
    # Issue #17: under weak light a face can answer below its onset threshold while a bright shirt answers clearly.
    # The face's mean change still pushes towards the colour, so the step is unclear, not neck-only.
    ctx = synth.context(kind="genuine", turn=None, noise=noise, seed=seed, echo_gain=0.05, neck_gain=8.0)
    r = light_face_neck.run(ctx)[0]
    assert not r.flag, r.explanation
