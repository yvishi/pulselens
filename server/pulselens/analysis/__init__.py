"""Analysis: the quality gate and the evidence families A to D (Ganeev). The engine calls `analyze` (CONTRACT §6)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from pulselens.analysis import specs
from pulselens.analysis.context import AnalysisContext, build_context
from pulselens.analysis.result import abstain
from pulselens.analysis.thresholds import Thresholds
from pulselens.bundle import load_bundle
from pulselens.contracts import CheckResult

__all__ = ["CHECKS", "analyze"]

log = logging.getLogger("pulselens.analysis")

# Each G task appends its check here. A check takes the context and returns its results ([] when it does not apply,
# for example the light check when the plan has no light). Every check is wrapped in result.guarded.
CHECKS: list[Callable[[AnalysisContext], list[CheckResult]]] = []


def _register() -> None:
    from pulselens.analysis.checks import sensor_stream

    CHECKS.extend([sensor_stream.run])


_register()


def _no_frames(explanation: str) -> list[CheckResult]:
    return [abstain(s.check_id, s.family, s.vote_group, ["quality.no_frames"], explanation) for s in specs.ALL]


def analyze(session_dir: Path, thresholds: Thresholds | None = None) -> list[CheckResult]:
    """Run every check of families A-D on a completed bundle. Never raises: a check that cannot judge returns status
    "abstain" with reason codes. Must finish in < 90 s for 900 frames on CPU."""
    try:
        thresholds = thresholds or Thresholds.load()
        bundle = load_bundle(Path(session_dir))
        if not bundle.frames:
            return _no_frames("The session has no video frames.")
        ctx = build_context(bundle, thresholds)
        if not ctx.readable.any():
            return _no_frames(f"None of the {ctx.n} video frames could be read.")
    except Exception:  # noqa: BLE001 -- analyze never raises
        log.exception("analysis could not read %s", session_dir)
        return _no_frames("The session could not be read.")
    out: list[CheckResult] = []
    for check in CHECKS:
        try:
            out.extend(check(ctx))
        except Exception:  # noqa: BLE001 -- a check without result.guarded; skipped, never fatal
            log.exception("check %s raised outside result.guarded", getattr(check, "__name__", check))
    return out
