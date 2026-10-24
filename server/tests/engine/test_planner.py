"""K3: planner rules (first match wins) and challenge safety."""

from __future__ import annotations

import itertools
import secrets

import pytest

from pulselens.config import load_config
from pulselens.contracts import ColourStep, DigitStep, NodStep, Plan, Preflight, TurnStep
from pulselens.engine.planner import MODE_REASONS, make_challenge, plan_session, rng_for_nonce
from pulselens.engine.reason_text import REASON_TEXT

CFG = load_config()


def pre(**over) -> Preflight:
    base = dict(
        user_agent="test", platform="desktop", browser="Brave 155", camera_label="USB2.0 HD UVC WebCam", width=640,
        height=480, measured_fps=30.0, dropped_frame_ratio=0.0, blur=120.0, brightness=120.0, face_found=True,
        face_fraction=0.1, controls=[], gyro=False, no_flash_requested=False, clock="captureTime", probe=[],
    )
    return Preflight(**{**base, **over})


def test_rule1_no_flash() -> None:
    for plan in (plan_session(pre(), True, CFG), plan_session(pre(no_flash_requested=True), False, CFG)):
        assert (plan.mode, plan.run_light, plan.run_turn, plan.agent_questions) == ("NO_FLASH", False, True, True)
        assert plan.reasons == ["mode.no_flash.requested"]


def test_rule2_too_bright() -> None:
    plan = plan_session(pre(brightness=230), False, CFG)
    assert (plan.mode, plan.run_light, plan.agent_questions) == ("NO_FLASH", False, True)
    assert plan.reasons == ["mode.no_flash.too_bright"]


def test_rule3_low_fps() -> None:
    plan = plan_session(pre(measured_fps=10.4), False, CFG)  # the dim-room webcam measured on the old prototype
    assert (plan.mode, plan.run_light, plan.run_turn, plan.agent_questions) == ("CONSTRAINED", False, True, True)
    assert plan.reasons == ["mode.constrained.fps_too_low_for_light"]


def test_rule4_capable() -> None:
    plan = plan_session(pre(measured_fps=30, brightness=120, face_fraction=0.1), False, CFG)
    assert (plan.mode, plan.run_light, plan.run_turn, plan.agent_questions) == ("CAPABLE", True, True, False)
    assert plan.reasons == ["mode.capable.ok"]


def test_rule5_constrained_dim() -> None:
    plan = plan_session(pre(measured_fps=25, brightness=30), False, CFG)
    assert (plan.mode, plan.run_light, plan.agent_questions) == ("CONSTRAINED", True, False)
    assert "mode.constrained.dim" in plan.reasons


def test_rule5_lists_every_failed_condition() -> None:
    plan = plan_session(pre(measured_fps=15.6, brightness=30, face_fraction=0.01), False, CFG)
    assert plan.reasons == ["mode.constrained.fps", "mode.constrained.dim", "mode.constrained.small_face"]


def test_no_face_adds_a_reason_and_agent_questions() -> None:
    plan = plan_session(pre(face_found=False, face_fraction=0.0), False, CFG)
    assert plan.reasons[-1] == "mode.face_not_found" and plan.agent_questions


def test_first_match_wins() -> None:
    # A no-flash request beats every camera problem; too bright beats low fps.
    assert plan_session(pre(measured_fps=5, brightness=250), True, CFG).reasons == ["mode.no_flash.requested"]
    assert plan_session(pre(measured_fps=5, brightness=250), False, CFG).reasons == ["mode.no_flash.too_bright"]


def test_every_reason_has_text() -> None:
    assert set(MODE_REASONS) <= set(REASON_TEXT)
    grid = itertools.product([True, False], [True, False], [5, 15, 25, 30], [10, 30, 120, 220, 230], [0.0, 0.01, 0.1],
                             [True, False])
    for session_nf, req_nf, fps, light, face, found in grid:
        p = plan_session(pre(no_flash_requested=req_nf, measured_fps=fps, brightness=light, face_fraction=face,
                             face_found=found), session_nf, CFG)
        assert p.reasons and set(p.reasons) <= set(MODE_REASONS), p.reasons


def _plan(mode: str) -> Plan:
    light = mode != "NO_FLASH"
    return Plan(mode=mode, run_light=light, run_turn=True, agent_questions=not light, reasons=[])


def _changes(steps: list) -> list[int]:
    """Every moment the screen colour changes: each colour step's start and end."""
    colours = [s for s in steps if isinstance(s, ColourStep)]
    return sorted(t for s in colours for t in (s.start_offset_ms, s.start_offset_ms + s.dwell_ms))


@pytest.mark.parametrize("mode", ["CAPABLE", "CONSTRAINED", "NO_FLASH"])
def test_challenge_safety(mode: str) -> None:
    for seed in range(200):
        ch = make_challenge(_plan(mode), "s1", f"nonce-{seed}", rng_for_nonce(f"nonce-{seed}"), CFG)
        colours = [s for s in ch.steps if isinstance(s, ColourStep)]
        turns = [s for s in ch.steps if isinstance(s, TurnStep)]
        for s in colours:
            assert 15 < s.hue_deg < 345, f"saturated red hue {s.hue_deg}"
        assert len({s.hue_deg for s in colours}) == len(colours)  # sampled without replacement
        spans = [(s.start_offset_ms, s.start_offset_ms + (s.dwell_ms if isinstance(s, ColourStep) else s.duration_ms))
                 for s in ch.steps]
        assert all(a_end <= b_start for (_, a_end), (b_start, _) in zip(spans, spans[1:], strict=False)), "overlap"
        assert [s.start_offset_ms for s in ch.steps] == sorted(s.start_offset_ms for s in ch.steps)
        changes = _changes(ch.steps)
        assert all(sum(t <= c < t + 1000 for c in changes) <= 3 for t in changes), "more than 3 changes in 1 s"
        assert ch.total_ms == spans[-1][1] + 1500  # the tail: a slow head is back from the turn before capture ends
        assert len(turns) == 1 and turns[0].step_id == "t0"
        expected = {"CAPABLE": 6, "CONSTRAINED": 4, "NO_FLASH": 0}[mode]
        assert [s.step_id for s in colours] == [f"c{k}" for k in range(expected)]


def test_turn_starts_after_the_gap_or_at_zero() -> None:
    ch = make_challenge(_plan("CAPABLE"), "s1", "n", rng_for_nonce("n"), CFG)
    last_colour = [s for s in ch.steps if isinstance(s, ColourStep)][-1]
    turn = next(s for s in ch.steps if isinstance(s, TurnStep))
    assert turn.start_offset_ms == last_colour.start_offset_ms + last_colour.dwell_ms + CFG["challenge"]["turn_gap_ms"]
    no_flash = make_challenge(_plan("NO_FLASH"), "s1", "n", rng_for_nonce("n"), CFG)
    assert no_flash.steps[0].start_offset_ms == 0


def test_challenge_random_per_nonce() -> None:
    def hues(nonce: str) -> list[int]:
        ch = make_challenge(_plan("CAPABLE"), "s1", nonce, rng_for_nonce(nonce), CFG)
        return [s.hue_deg for s in ch.steps if isinstance(s, ColourStep)]

    different = sum(hues(secrets.token_hex(16)) != hues(secrets.token_hex(16)) for _ in range(100))
    assert different >= 95
    nonce = secrets.token_hex(16)
    a = make_challenge(_plan("CAPABLE"), "s1", nonce, rng_for_nonce(nonce), CFG)
    b = make_challenge(_plan("CAPABLE"), "s1", nonce, rng_for_nonce(nonce), CFG)
    assert a == b


@pytest.mark.parametrize("mode", ["CAPABLE", "CONSTRAINED", "NO_FLASH"])
def test_extra_prompts_follow_the_turn_in_every_mode(mode: str) -> None:
    c = CFG["challenge"]
    assert c["extra_prompts"] is True
    for seed in range(100):
        ch = make_challenge(_plan(mode), "s1", f"nonce-{seed}", rng_for_nonce(f"nonce-{seed}"), CFG)
        turn = next(s for s in ch.steps if isinstance(s, TurnStep))
        nod, digits = ch.steps[-4], ch.steps[-3:]
        assert isinstance(nod, NodStep) and nod.step_id == "n0" and nod.duration_ms == c["nod_ms"]
        assert nod.start_offset_ms == turn.start_offset_ms + turn.duration_ms + c["nod_gap_ms"]
        assert all(isinstance(d, DigitStep) for d in digits) and [d.step_id for d in digits] == ["d0", "d1", "d2"]
        assert len({d.digit for d in digits}) == 3 and all(0 <= d.digit <= 9 for d in digits)
        assert digits[0].start_offset_ms == nod.start_offset_ms + nod.duration_ms + c["digit_first_gap_ms"]
        lo, hi = c["digit_gap_ms"]
        for a, b in zip(digits, digits[1:], strict=False):
            assert lo <= b.start_offset_ms - (a.start_offset_ms + a.duration_ms) <= hi
        assert ch.total_ms == digits[-1].start_offset_ms + digits[-1].duration_ms + 1500


def test_extra_prompts_off_is_the_challenge_from_before() -> None:
    off = {**CFG, "challenge": {**CFG["challenge"], "extra_prompts": False}}
    for seed in range(50):
        nonce = f"nonce-{seed}"
        on_ch = make_challenge(_plan("CAPABLE"), "s1", nonce, rng_for_nonce(nonce), CFG)
        off_ch = make_challenge(_plan("CAPABLE"), "s1", nonce, rng_for_nonce(nonce), off)
        assert not any(isinstance(s, NodStep | DigitStep) for s in off_ch.steps)
        assert off_ch.steps == on_ch.steps[: len(off_ch.steps)]  # the colours and the turn are the same draws
        assert off_ch.total_ms == off_ch.steps[-1].start_offset_ms + off_ch.steps[-1].duration_ms + 1500


def test_digits_are_unpredictable_per_nonce() -> None:
    def digits(nonce: str) -> list[int]:
        ch = make_challenge(_plan("NO_FLASH"), "s1", nonce, rng_for_nonce(nonce), CFG)
        return [s.digit for s in ch.steps if isinstance(s, DigitStep)]

    assert sum(digits(secrets.token_hex(16)) != digits(secrets.token_hex(16)) for _ in range(100)) >= 95
