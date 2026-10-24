"""K6: fusion and outcomes, table-driven (docs/CONTRACT.md section 8)."""

from __future__ import annotations

import pytest

from pulselens.contracts import CheckResult, Decision, Plan
from pulselens.engine.fusion import customer_message, fuse
from pulselens.engine.reason_text import REASON_TEXT


def r(family: str, status: str = "usable", flag: bool = False, group: str = "X", *, codes: list[str] | None = None,
      source: str = "rule", explanation: str | None = None, check_id: str | None = None,
      voting: bool = True) -> CheckResult:
    usable = status == "usable"
    return CheckResult(
        check_id=check_id or f"test.{family.lower()}.{group}", family=family, vote_group=f"{family}.{group}",
        status=status, risk=(0.9 if flag else 0.1) if usable else None, flag=flag and usable and voting,
        quality=1.0 if usable else 0.2, reason_codes=codes or [],
        explanation=explanation or f"{family} {group} {status}{' flag' if flag else ''}.", threshold_source=source,
        voting=voting,
    )


def turn(status: str = "usable", flag: bool = False, codes: list[str] | None = None) -> CheckResult:
    return r("D", status, flag, group="turn", codes=codes, check_id="turn.follow")


def light(status: str = "usable", flag: bool = False, codes: list[str] | None = None) -> CheckResult:
    return r("C", status, flag, group="response", codes=codes, check_id="light.response")


def plan(mode: str = "CAPABLE", run_turn: bool = True) -> Plan:
    return Plan(mode=mode, run_light=mode != "NO_FLASH", run_turn=run_turn, agent_questions=mode == "NO_FLASH",
                reasons=[])


CLEAN = [r("B"), r("C"), turn()]
NOT_DONE = ["turn.not_performed"]
# S2: a YouTube face replayed to the camera. Sensor checks clean (a real camera filmed the screen), light answered (the
# glossy screen reflected the flash), the background and face/neck checks abstained, the turn was not performed,
# and SBI (measured only) was the only usable result in D. It passed the old table.
REPLAY = [r("B"), light(), r("C", "abstain", group="relative", codes=["light.background_hidden"]),
          turn("abstain", codes=NOT_DONE), r("D", group="detector", check_id="visual.sbi", voting=False),
          r("A", group="pulse", check_id="pulse.coherence", voting=False)]

# (name, results, plan mode, attempt, outcome, step_up)
CASES = [
    ("protocol_error_wins", CLEAN + [r("B", "protocol_error", group="protocol")], "CAPABLE", 1, "HUMAN_REVIEW", None),
    ("two_families", [r("B", flag=True), r("C", flag=True), r("D")], "CAPABLE", 1, "HUMAN_REVIEW", None),
    ("three_families", [r("B", flag=True), r("C", flag=True), r("D", flag=True)], "CAPABLE", 1, "HUMAN_REVIEW", None),
    ("same_family_two_checks_is_one_family",
     [r("B", flag=True, group="stream"), r("B", flag=True, group="probe"), r("C"), r("D")], "CAPABLE", 1,
     "RETRY_STEP_UP", "fresh_challenge"),
    ("one_family_no_flash", [r("B"), r("C", "abstain"), r("D", flag=True)], "NO_FLASH", 1, "RETRY_STEP_UP",
     "agent_checks"),
    ("one_family_attempt2", [r("B", flag=True), r("C"), r("D")], "CAPABLE", 2, "RETRY_STEP_UP", "agent_checks"),
    ("low_coverage_light_quality",
     [r("B"), r("C", "abstain", codes=["quality.too_dark"]), r("D", "abstain")], "CAPABLE", 1, "RETRY_STEP_UP",
     "no_flash"),
    ("low_coverage_light_quality_in_no_flash",
     [r("B"), r("C", "abstain", codes=["quality.too_dark"]), r("D", "abstain")], "NO_FLASH", 1, "RETRY_STEP_UP",
     "agent_checks"),
    ("low_coverage_other_reason", [r("B"), r("C", "abstain", codes=["light.weak_face_echo"])], "CAPABLE", 1,
     "RETRY_STEP_UP", "agent_checks"),
    ("low_coverage_attempt3", [r("B"), r("C", "abstain", codes=["quality.too_dark"])], "CAPABLE", 3,
     "RETRY_STEP_UP", "assisted_kyc"),
    ("nothing_ran", [], "CAPABLE", 1, "RETRY_STEP_UP", "agent_checks"),
    ("abstain_never_counts", [r("B"), r("C", "abstain"), turn(), r("C", "abstain", group="relative")], "CAPABLE", 1,
     "PASS", None),
    ("pass", CLEAN, "CAPABLE", 1, "PASS", None),
    ("replay_with_no_turn_is_a_fresh_challenge", REPLAY, "CAPABLE", 1, "RETRY_STEP_UP", "fresh_challenge"),
    ("turn_not_done_again_goes_to_the_agent", REPLAY, "CAPABLE", 2, "RETRY_STEP_UP", "agent_checks"),
    ("measured_only_results_cover_no_family",
     [r("B"), r("C", "abstain"), r("D", group="detector", check_id="visual.sbi", voting=False)], "CAPABLE", 1,
     "RETRY_STEP_UP", "agent_checks"),
    ("no_flags_but_turn_unverified_is_not_a_pass",
     [r("B"), r("C"), r("D", group="identity"), turn("abstain", codes=["quality.too_dark"])], "CAPABLE", 1,
     "RETRY_STEP_UP", "agent_checks"),
    ("without_a_turn_the_light_must_answer", [r("B"), light(), r("D", group="identity")], "CAPABLE_NO_TURN", 1,
     "PASS", None),
    ("without_a_turn_and_no_light_answer_is_not_a_pass",
     [r("B"), light("abstain", codes=["light.weak_face_echo"]), r("C", group="relative"), r("D", group="identity")],
     "CAPABLE_NO_TURN", 1, "RETRY_STEP_UP", "agent_checks"),
]


@pytest.mark.parametrize(("name", "results", "mode", "attempt", "outcome", "step_up"), CASES, ids=[c[0] for c in CASES])
def test_outcome_table(name, results, mode, attempt, outcome, step_up) -> None:
    p = plan("CAPABLE", run_turn=False) if mode == "CAPABLE_NO_TURN" else plan(mode)
    d = fuse(results, p, attempt, decided_at_ms=0)
    assert (d.outcome, d.step_up) == (outcome, step_up)
    assert [f.family for f in d.families] == ["A", "B", "C", "D"]


def test_fuse_stamps_the_given_time() -> None:
    assert fuse(CLEAN, plan(), 1, decided_at_ms=5).decided_at_ms == 5


def test_protocol_error_marks_the_violation() -> None:
    d = fuse(CLEAN + [r("B", "protocol_error", group="protocol", explanation="Frame times went backwards.")],
             plan(), 1, decided_at_ms=0)
    assert d.integrity_violation and d.reasons[0] == REASON_TEXT["fusion.integrity_violation"]
    assert "Frame times went backwards." in d.reasons


def test_correlated_cues_one_vote() -> None:
    # sensor.cadence and sensor.duplicates share B.stream: B counts once, so with C and D clean it is one family.
    stream = [r("B", flag=True, group="stream"), r("B", flag=True, group="stream")]
    d = fuse(stream + [r("C"), r("D")], plan(), 1, decided_at_ms=0)
    b = d.families[1]
    assert (b.state, b.usable_checks, b.flagged_checks) == ("flag", 2, 2)
    assert d.outcome == "RETRY_STEP_UP"


def test_family_a_never_votes() -> None:
    all_flagged = fuse([r("A", flag=True), r("B", flag=True), r("C", flag=True), r("D")], plan(), 1, decided_at_ms=0)
    assert all_flagged.outcome == "HUMAN_REVIEW"
    a_and_b = fuse([r("A", flag=True), r("B", flag=True), r("C"), r("D")], plan(), 1, decided_at_ms=0)
    assert (a_and_b.outcome, a_and_b.step_up) == ("RETRY_STEP_UP", "fresh_challenge")
    assert a_and_b.families[0].state == "flag"
    assert any("not used in the decision" in x for x in a_and_b.reasons)


def test_family_states() -> None:
    d = fuse([r("B"), r("C", "abstain"), r("C", "abstain", group="relative")], plan(), 1, decided_at_ms=0)
    assert [f.state for f in d.families] == ["not_run", "not_raised", "abstained", "not_run"]


def test_reasons_order_and_family_sentences() -> None:
    results = [r("B", flag=True, explanation="72% of frames repeated."), r("C", "abstain", explanation="Too dark."),
               r("D")]
    d = fuse(results, plan(), 1, decided_at_ms=0)
    assert d.reasons[0] == REASON_TEXT["fusion.one_family"]
    assert d.reasons[1] == REASON_TEXT["fusion.step_up.fresh_challenge"]
    assert d.reasons[2] == "Sensor and stream: 72% of frames repeated."
    assert d.reasons[3] == "Light challenge could not judge: Too dark."
    assert d.families[1].reasons == ["72% of frames repeated."]
    assert d.families[2].reasons == ["Too dark."]


def test_provisional_flag() -> None:
    assert fuse([r("B", source="provisional"), r("C"), r("D")], plan(), 1, decided_at_ms=0).provisional
    assert not fuse(CLEAN, plan(), 1, decided_at_ms=0).provisional
    # An abstained provisional check does not make the decision provisional.
    late = CLEAN + [r("C", "abstain", group="relative", source="provisional")]
    assert not fuse(late, plan(), 1, decided_at_ms=0).provisional


def test_every_fusion_code_has_text() -> None:
    needed = ["fusion.integrity_violation", "fusion.two_families", "fusion.one_family", "fusion.low_coverage",
              "fusion.challenge_not_done", "fusion.liveness_not_shown", "fusion.pass"]
    needed += [f"fusion.step_up.{s}" for s in ("fresh_challenge", "no_flash", "agent_checks", "assisted_kyc")]
    assert [c for c in needed if c not in REASON_TEXT] == []


def _decision(outcome: str, step_up: str | None) -> Decision:
    d = fuse(CLEAN, plan(), 1, decided_at_ms=0)
    return d.model_copy(update={"outcome": outcome, "step_up": step_up})


@pytest.mark.parametrize(("outcome", "step_up", "message"), [
    ("PASS", None, "continue"),
    ("RETRY_STEP_UP", "fresh_challenge", "please_retry"),
    ("RETRY_STEP_UP", "no_flash", "please_wait"),
    ("RETRY_STEP_UP", "agent_checks", "please_wait"),
    ("RETRY_STEP_UP", "assisted_kyc", "assisted_route"),
    ("HUMAN_REVIEW", None, "please_wait"),
])
def test_customer_message_mapping(outcome: str, step_up: str | None, message: str) -> None:
    assert customer_message("done", _decision(outcome, step_up)).message == message


def test_customer_waits_until_done() -> None:
    for state in ("created", "preflight", "capturing", "analysing", "expired"):
        assert customer_message(state, _decision("PASS", None)).message == "please_wait"
    assert customer_message("done", None).message == "please_wait"
