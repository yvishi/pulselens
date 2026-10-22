"""Building CheckResults. Every check returns through `result` or `abstain`, and is wrapped by `guarded`.

Rules (docs/tasks/ganeev.md): checks never raise; `risk` is None and `flag` false unless the result is usable.
"""

from __future__ import annotations

import functools
import logging
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from pulselens.contracts import CheckResult, Family, Plot, ThresholdSource

log = logging.getLogger("pulselens.analysis")


@dataclass(frozen=True)
class CheckSpec:
    """Who a check is (CONTRACT section 9): what `guarded` needs to abstain in its name."""

    check_id: str
    family: Family
    vote_group: str


def clean_features(features: Mapping[str, float | int | None]) -> dict[str, float]:
    """CheckResult.features holds finite floats only."""
    return {k: float(v) for k, v in features.items() if v is not None and math.isfinite(float(v))}


def _unit(x: float) -> float:
    return float(min(1.0, max(0.0, x))) if math.isfinite(x) else 0.0


def result(
    check_id: str,
    family: Family,
    vote_group: str,
    *,
    risk: float,
    flag_at: float,
    quality: float,
    features: Mapping[str, float | int | None],
    reasons: list[str],
    explanation: str,
    source: ThresholdSource,
    window_id: str | None = None,
    plot: Plot | None = None,
    uncertainty: float | None = None,
    voting: bool = True,
) -> CheckResult:
    """A usable result. flag = risk >= flag_at (and the check votes); risk is clipped to 0..1."""
    risk = _unit(risk)
    return CheckResult(
        check_id=check_id,
        family=family,
        vote_group=vote_group,
        status="usable",
        risk=risk,
        flag=voting and risk >= flag_at,
        quality=_unit(quality),
        uncertainty=uncertainty,
        features=clean_features(features),
        reason_codes=reasons,
        explanation=explanation,
        window_id=window_id,
        threshold_source=source,
        plot=plot,
    )


def abstain(
    check_id: str,
    family: Family,
    vote_group: str,
    reasons: list[str],
    explanation: str,
    quality: float = 0.0,
    *,
    features: Mapping[str, float | int | None] | None = None,
    window_id: str | None = None,
    source: ThresholdSource = "provisional",
) -> CheckResult:
    return CheckResult(
        check_id=check_id,
        family=family,
        vote_group=vote_group,
        status="abstain",
        risk=None,
        flag=False,
        quality=_unit(quality),
        features=clean_features(features or {}),
        reason_codes=reasons,
        explanation=explanation,
        window_id=window_id,
        threshold_source=source,
    )


Check = Callable[[Any], list[CheckResult]]


def guarded(*specs: CheckSpec) -> Callable[[Check], Check]:
    """Decorator: any exception inside the check becomes one abstain per check it emits, with
    `quality.check_error`; the traceback goes to the server log."""

    def wrap(fn: Check) -> Check:
        @functools.wraps(fn)
        def safe(ctx: Any) -> list[CheckResult]:
            try:
                return fn(ctx)
            except Exception as e:  # noqa: BLE001 -- by design: checks never raise
                log.exception("check %s failed", fn.__name__)
                return [
                    abstain(s.check_id, s.family, s.vote_group, ["quality.check_error"],
                            f"Could not be measured ({type(e).__name__}).")
                    for s in specs
                ]

        safe.specs = specs  # type: ignore[attr-defined]
        return safe

    return wrap
