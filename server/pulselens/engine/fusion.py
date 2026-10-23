"""Evidence fusion and policy outcomes (service steps 4 and 5; docs/CONTRACT.md section 8, exactly).

1. Gate: only usable results count. Abstain never counts for or against.
2. Group: results with the same vote_group are one vote (flags if any member flags).
3. Family state: flag, not_raised, abstained, not_run.
4. Family A is reported but never votes.
5. Outcome: first matching rule wins.
PulseLens recommends; the agent decides.
"""

from __future__ import annotations

import time
from collections import defaultdict

from pulselens.contracts import (
    CheckResult,
    CustomerMessage,
    CustomerStatus,
    Decision,
    Family,
    FamilyState,
    FamilySummary,
    Outcome,
    Plan,
    SessionState,
    StepUp,
)
from pulselens.engine.reason_text import reason_text

FAMILIES: tuple[Family, ...] = ("A", "B", "C", "D")
VOTING: tuple[Family, ...] = ("B", "C", "D")
FAMILY_NAMES = {"A": "Pulse", "B": "Sensor and stream", "C": "Light challenge", "D": "Visual and motion"}


def _family_state(results: list[CheckResult]) -> FamilyState:
    if not results:
        return "not_run"
    usable = [r for r in results if r.status == "usable"]
    if not usable:
        return "abstained"
    groups: dict[str, bool] = defaultdict(bool)
    for r in usable:
        groups[r.vote_group] |= r.flag
    return "flag" if any(groups.values()) else "not_raised"


def _summary(family: Family, results: list[CheckResult]) -> FamilySummary:
    usable = [r for r in results if r.status == "usable"]
    flagged = [r for r in usable if r.flag]
    abstained = [r for r in results if r.status == "abstain"]
    return FamilySummary(
        family=family,
        state=_family_state(results),
        usable_checks=len(usable),
        flagged_checks=len(flagged),
        reasons=[r.explanation for r in flagged] + [r.explanation for r in abstained],
    )


def _low_coverage_step_up(
    light: list[CheckResult], light_state: FamilyState, plan: Plan | None, attempt: int
) -> StepUp:
    if attempt >= 3:
        return "assisted_kyc"
    light_quality = light_state == "abstained" and any(c.startswith("quality.") for r in light for c in r.reason_codes)
    if light_quality and (plan is None or plan.mode != "NO_FLASH"):
        return "no_flash"
    return "agent_checks"


def _outcome(
    results: list[CheckResult], by_family: dict[Family, list[CheckResult]], state: dict[Family, FamilyState],
    plan: Plan | None, attempt: int,
) -> tuple[Outcome, str, StepUp | None]:
    """CONTRACT section 8, rule 5: the first matching row wins."""
    flagged = [f for f in VOTING if state[f] == "flag"]
    covered = [f for f in VOTING if state[f] in ("flag", "not_raised")]
    if any(r.status == "protocol_error" for r in results):
        return "HUMAN_REVIEW", "fusion.integrity_violation", None
    if len(flagged) >= 2:
        return "HUMAN_REVIEW", "fusion.two_families", None
    if len(flagged) == 1:
        no_flash = plan is not None and plan.mode == "NO_FLASH"
        return "RETRY_STEP_UP", "fusion.one_family", "agent_checks" if no_flash or attempt >= 2 else "fresh_challenge"
    if len(covered) < 2:
        return "RETRY_STEP_UP", "fusion.low_coverage", _low_coverage_step_up(by_family["C"], state["C"], plan, attempt)
    return "PASS", "fusion.pass", None


def _reasons(code: str, step_up: StepUp | None, results: list[CheckResult], summaries: list[FamilySummary],
             by_family: dict[Family, list[CheckResult]]) -> list[str]:
    """The outcome sentence, the step-up, protocol errors, then one sentence per flagged and per abstained family."""
    reasons = [reason_text(code)]
    if step_up:
        reasons.append(reason_text(f"fusion.step_up.{step_up}"))
    reasons += [r.explanation for r in results if r.status == "protocol_error"]
    for s in summaries:
        if s.state == "flag":
            flags = [r.explanation for r in by_family[s.family] if r.status == "usable" and r.flag]
            note = " (reported only, not used in the decision)" if s.family == "A" else ""
            reasons.append(f"{FAMILY_NAMES[s.family]}{note}: {' '.join(flags)}")
    reasons += [f"{FAMILY_NAMES[s.family]} could not judge: {' '.join(s.reasons)}"
                for s in summaries if s.state == "abstained"]
    return reasons


def fuse(results: list[CheckResult], plan: Plan | None, attempt: int) -> Decision:
    by_family: dict[Family, list[CheckResult]] = {f: [] for f in FAMILIES}
    for r in results:
        by_family[r.family].append(r)
    summaries = [_summary(f, by_family[f]) for f in FAMILIES]
    state = {s.family: s.state for s in summaries}
    outcome, code, step_up = _outcome(results, by_family, state, plan, attempt)
    return Decision(
        outcome=outcome,
        step_up=step_up,
        families=summaries,
        reasons=_reasons(code, step_up, results, summaries, by_family),
        integrity_violation=code == "fusion.integrity_violation",
        provisional=any(r.status == "usable" and r.threshold_source == "provisional" for r in results),
        decided_at_ms=int(time.time() * 1000),
    )


def customer_message(state: SessionState, decision: Decision | None) -> CustomerStatus:
    """The only result a customer ever sees (CONTRACT section 2): never a score, family, check or outcome."""
    message: CustomerMessage = "please_wait"
    if state == "done" and decision is not None:
        if decision.outcome == "PASS":
            message = "continue"
        elif decision.outcome == "RETRY_STEP_UP":
            message = {"fresh_challenge": "please_retry", "assisted_kyc": "assisted_route"}.get(
                decision.step_up or "", "please_wait"
            )
    return CustomerStatus(state=state, message=message)
