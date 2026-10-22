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


def _low_coverage_step_up(by_family: dict[Family, list[CheckResult]], plan: Plan | None, attempt: int) -> StepUp:
    if attempt >= 3:
        return "assisted_kyc"
    light = by_family["C"]
    light_quality = _family_state(light) == "abstained" and any(
        code.startswith("quality.") for r in light for code in r.reason_codes
    )
    if light_quality and (plan is None or plan.mode != "NO_FLASH"):
        return "no_flash"
    return "agent_checks"


def fuse(results: list[CheckResult], plan: Plan | None, attempt: int) -> Decision:
    by_family: dict[Family, list[CheckResult]] = {f: [] for f in FAMILIES}
    for r in results:
        by_family[r.family].append(r)
    summaries = [_summary(f, by_family[f]) for f in FAMILIES]
    state = {s.family: s.state for s in summaries}
    flagged = [f for f in VOTING if state[f] == "flag"]
    covered = [f for f in VOTING if state[f] in ("flag", "not_raised")]
    integrity_violation = any(r.status == "protocol_error" for r in results)

    step_up: StepUp | None = None
    if integrity_violation:
        outcome, code = "HUMAN_REVIEW", "fusion.integrity_violation"
    elif len(flagged) >= 2:
        outcome, code = "HUMAN_REVIEW", "fusion.two_families"
    elif len(flagged) == 1:
        outcome, code = "RETRY_STEP_UP", "fusion.one_family"
        no_flash = plan is not None and plan.mode == "NO_FLASH"
        step_up = "agent_checks" if no_flash or attempt >= 2 else "fresh_challenge"
    elif len(covered) < 2:
        outcome, code = "RETRY_STEP_UP", "fusion.low_coverage"
        step_up = _low_coverage_step_up(by_family, plan, attempt)
    else:
        outcome, code = "PASS", "fusion.pass"

    reasons = [reason_text(code)]
    if step_up:
        reasons.append(reason_text(f"fusion.step_up.{step_up}"))
    if integrity_violation:
        reasons += [r.explanation for r in results if r.status == "protocol_error"]
    for s in summaries:
        if s.state == "flag":
            flags = [r.explanation for r in by_family[s.family] if r.status == "usable" and r.flag]
            note = " (reported only, not used in the decision)" if s.family == "A" else ""
            reasons.append(f"{FAMILY_NAMES[s.family]}{note}: {' '.join(flags)}")
    for s in summaries:
        if s.state == "abstained":
            reasons.append(f"{FAMILY_NAMES[s.family]} could not judge: {' '.join(s.reasons)}")

    return Decision(
        outcome=outcome,
        step_up=step_up,
        families=summaries,
        reasons=reasons,
        integrity_violation=integrity_violation,
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
