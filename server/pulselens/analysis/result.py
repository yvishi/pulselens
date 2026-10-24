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

from pulselens.analysis.thresholds import Thresholds
from pulselens.contracts import CheckResult, Family, Plot

log = logging.getLogger("pulselens.analysis")


@dataclass(frozen=True)
class CheckSpec:
    """Who a check is (CONTRACT section 9): what `result`, `abstain` and `guarded` need to name it."""

    check_id: str
    family: Family
    vote_group: str
    never_flags: bool = False  # supporting or logged only (sensor.prnu, pulse.coherence): flag stays false


def clean_features(features: Mapping[str, float | int | None]) -> dict[str, float]:
    """CheckResult.features holds finite floats only."""
    return {k: float(v) for k, v in features.items() if v is not None and math.isfinite(float(v))}


def _unit(x: float) -> float:
    return float(min(1.0, max(0.0, x))) if math.isfinite(x) else 0.0


def result(
    spec: CheckSpec,
    t: Thresholds,
    *,
    risk: float,
    quality: float,
    features: Mapping[str, float | int | None],
    reasons: list[str],
    explanation: str,
    window_id: str | None = None,
    plot: Plot | None = None,
    uncertainty: float | None = None,
) -> CheckResult:
    """A usable result. Its threshold, threshold source and vote come from `t`: flag = risk >= flag_at, unless the
    check does not vote (`voting: false` at S3, or a spec that never flags). Risk is clipped to 0..1."""
    risk = _unit(risk)
    votes = t.voting(spec.check_id) and not spec.never_flags
    return CheckResult(
        check_id=spec.check_id,
        family=spec.family,
        vote_group=spec.vote_group,
        status="usable",
        risk=risk,
        flag=votes and risk >= t.flag_at(spec.check_id),
        quality=_unit(quality),
        uncertainty=uncertainty,
        features=clean_features(features),
        reason_codes=reasons,
        explanation=explanation,
        window_id=window_id,
        threshold_source=t.source(spec.check_id),
        plot=plot,
        voting=votes,
    )


def abstain(
    spec: CheckSpec,
    reasons: list[str],
    explanation: str,
    quality: float = 0.0,
    *,
    features: Mapping[str, float | int | None] | None = None,
    window_id: str | None = None,
) -> CheckResult:
    """No judgement: risk None, flag false. Abstaining is never attack evidence."""
    return CheckResult(
        check_id=spec.check_id,
        family=spec.family,
        vote_group=spec.vote_group,
        status="abstain",
        risk=None,
        flag=False,
        quality=_unit(quality),
        features=clean_features(features or {}),
        reason_codes=reasons,
        explanation=explanation,
        window_id=window_id,
        threshold_source="provisional",
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
                return [abstain(s, ["quality.check_error"], f"Could not be measured ({type(e).__name__}).")
                        for s in specs]

        return safe

    return wrap
