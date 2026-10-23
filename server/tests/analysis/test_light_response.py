from pathlib import Path

import pytest

from pulselens.analysis import analyze
from pulselens.analysis.checks.light_response import run, step_echoes
from pulselens.analysis.context import AnalysisContext, build_context
from pulselens.analysis.thresholds import Thresholds
from pulselens.bundle import load_bundle


def _ctx(path: Path) -> AnalysisContext:
    return build_context(load_bundle(path), Thresholds.load())


def _one(ctx: AnalysisContext):
    results = run(ctx)
    assert len(results) == 1
    r = results[0]
    assert r.check_id == "light.response" and r.family == "C" and r.vote_group == "C.response"
    assert r.window_id == "all" and r.threshold_source == "provisional"
    return r


@pytest.mark.parametrize("fps", [30.0, 15.0])
def test_genuine_is_usable_and_not_flagged(synth, fps: float) -> None:
    r = _one(synth.context(kind="genuine", fps=fps, turn=None))
    assert r.status == "usable" and not r.flag, r.explanation
    assert r.features["steps_valid"] == 6 and r.features["steps_answered"] >= 5
    assert r.features["steps_order_ok"] >= 5
    assert r.plot is not None and r.plot.kind == "echo"
    assert all(len(points) <= 300 for points in r.plot.series.values())
    assert [label for _, label in r.plot.markers] == [f"c{k}" for k in range(6)]


def test_the_explanation_carries_the_real_numbers(synth) -> None:
    r = _one(synth.context(kind="genuine", turn=None))
    answered, delay = int(r.features["steps_answered"]), r.features["median_delay_ms"]
    assert f"answered {answered} of 6 colour steps" in r.explanation
    assert f"{delay:.0f} ms after each" in r.explanation and "0 to 300 ms" in r.explanation


@pytest.mark.parametrize("kind", ["replay", "virtual_camera"])
def test_no_face_echo_is_flagged(synth, kind: str) -> None:
    r = _one(synth.context(kind=kind, turn=None))
    assert r.flag and r.risk >= 0.8 and "light.no_echo" in r.reason_codes
    assert r.features["steps_answered"] == 0


def test_swapped_colour_order_is_flagged_with_order_reasons(synth) -> None:
    r = _one(synth.context(kind="genuine", turn=None, swap_colours=True))
    assert r.flag and "light.wrong_order" in r.reason_codes, r.explanation
    assert r.features["steps_order_ok"] <= 2


def test_10_fps_abstains_with_low_fps(synth) -> None:
    r = _one(synth.context(kind="genuine", fps=10, turn=None))
    assert r.status == "abstain" and r.risk is None and not r.flag
    assert "quality.low_fps" in r.reason_codes


def test_three_valid_steps_abstain(synth) -> None:
    r = _one(synth.context(kind="genuine", n_colour=3, turn=None))
    assert r.status == "abstain" and "light.too_few_steps" in r.reason_codes


def test_no_face_abstains(synth) -> None:
    r = _one(synth.context(kind="genuine", turn=None, face_in_frames=False))
    assert r.status == "abstain" and "quality.no_face" in r.reason_codes


def test_light_not_in_the_plan_is_not_run(synth) -> None:
    assert run(synth.context(kind="genuine", n_colour=0)) == []


@pytest.mark.parametrize("delay", [60, 100, 150, 250])
def test_delays_are_recovered_within_one_frame(synth, delay: int) -> None:
    ctx = synth.context(kind="genuine", turn=None, delay_ms=delay, seed=delay)
    frame = 1000 / 30
    steps = step_echoes(ctx)
    assert len(steps) == 6
    for s in steps:
        assert s.onset.valid and s.onset.onset_ms is not None, s.onset.step_id
        assert abs(s.onset.onset_ms - delay) <= frame, (s.onset.step_id, s.onset.onset_ms)
    assert abs(_one(ctx).features["median_delay_ms"] - delay) <= frame


def test_a_noisy_genuine_session_still_answers(synth) -> None:
    r = _one(synth.context(kind="genuine", turn=None, noise=0.02, seed=7))
    assert r.status == "usable" and not r.flag, r.explanation


def test_analyze_includes_light_response(synth) -> None:
    results = {r.check_id: r for r in analyze(synth.session(kind="genuine"))}
    assert results["light.response"].status == "usable"


@pytest.mark.parametrize("kind", ["genuine", "replay"])
@pytest.mark.parametrize("noise", [0.06, 0.1])
def test_heavy_noise_is_never_a_flag(synth, kind: str, noise: float) -> None:
    # AGENTS.md rule 3: poor capture leads to a retry. A step too noisy to tell an echo from silence is unclear.
    r = _one(synth.context(kind=kind, turn=None, noise=noise, seed=3))
    assert not r.flag, r.explanation
    if r.status == "abstain":
        assert "light.too_few_steps" in r.reason_codes and "light.weak_face_echo" in r.reason_codes


def test_order_only_counts_steps_that_responded(synth) -> None:
    r = _one(synth.context(kind="replay", turn=None))
    assert r.features["steps_order_ok"] == 0
