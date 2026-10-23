"""CheckResult builders for the engine's own checks (integrity, analysis errors, fake analysis).

The engine's results are all family B and rule-based unless said otherwise; these builders keep the contract's
invariants in one place: only a usable result carries a risk, and only a usable result can flag.
"""

from __future__ import annotations

from pulselens.contracts import CheckResult, Family, ThresholdSource


def usable(check_id: str, explanation: str, *, risk: float = 0.0, flag: bool = False, family: Family = "B",
           vote_group: str = "B.protocol", features: dict[str, float] | None = None,
           reason_codes: list[str] | None = None, source: ThresholdSource = "rule") -> CheckResult:
    return CheckResult(check_id=check_id, family=family, vote_group=vote_group, status="usable", risk=risk, flag=flag,
                       quality=1.0, features=features or {}, reason_codes=reason_codes or [], explanation=explanation,
                       window_id="all", threshold_source=source)


def abstain(check_id: str, explanation: str, reason_codes: list[str], *, quality: float = 0.0,
            vote_group: str = "B.protocol", features: dict[str, float] | None = None) -> CheckResult:
    return CheckResult(check_id=check_id, family="B", vote_group=vote_group, status="abstain", risk=None, flag=False,
                       quality=quality, features=features or {}, reason_codes=reason_codes, explanation=explanation,
                       window_id="all", threshold_source="rule")


def protocol_error(check_id: str, explanation: str, reason_codes: list[str]) -> CheckResult:
    return CheckResult(check_id=check_id, family="B", vote_group="B.protocol", status="protocol_error", risk=None,
                       flag=False, quality=1.0, reason_codes=reason_codes, explanation=explanation, window_id="all",
                       threshold_source="rule")
