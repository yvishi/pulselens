"""Analysis runner (docs/tasks/keshav.md K4): runs on a worker thread after /complete.

1. load the bundle, 2. integrity (K5), 3. Ganeev's analyze() (or the fake one) with a timeout, 4. fusion (K6),
5. results.json and decision.json, then state done. It never leaves a session in "analysing": any failure becomes
an `analysis.error` result and the decision is still made.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from pathlib import Path

from pulselens.bundle import load_bundle
from pulselens.contracts import CheckResult, Decision
from pulselens.engine import fake_analysis
from pulselens.engine.fusion import fuse
from pulselens.engine.integrity import check_integrity
from pulselens.engine.store import SessionStore

log = logging.getLogger("pulselens.runner")
Analyze = Callable[[Path], list[CheckResult]]

# A timed-out analysis keeps its thread (Python cannot kill one); a separate pool keeps it from blocking new runs.
_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="analyze")


def choose_analyze(fake: bool) -> tuple[Analyze, bool]:
    """(analyze, is_fake): the fake when asked for, or while pulselens.analysis has no analyze."""
    if not fake:
        try:
            from pulselens.analysis import analyze  # Ganeev
        except ImportError:
            analyze = None
        if callable(analyze):
            return analyze, False
    return fake_analysis.analyze, True


def analysis_error(explanation: str) -> CheckResult:
    return CheckResult(
        check_id="analysis.error", family="B", vote_group="B.analysis", status="abstain", risk=None, flag=False,
        quality=0.0, explanation=explanation, reason_codes=["analysis.error"], threshold_source="rule",
    )


def _analyze_with_timeout(analyze: Analyze, session_dir: Path, timeout_s: float) -> list[CheckResult]:
    future = _pool.submit(analyze, session_dir)
    try:
        results = future.result(timeout=timeout_s)
    except FutureTimeout:
        log.error("analysis of %s did not finish in %.0f s", session_dir.name, timeout_s)
        return [analysis_error(f"Analysis did not finish in {timeout_s:.0f} s.")]
    except Exception:
        log.exception("analysis of %s raised", session_dir.name)
        return [analysis_error("Analysis did not finish.")]
    if not isinstance(results, list) or not all(isinstance(r, CheckResult) for r in results):
        return [analysis_error("Analysis returned something other than check results.")]
    return results


def run_analysis(session_dir: Path, store: SessionStore, *, fake: bool = False, timeout_s: float = 120,
                 analyze: Analyze | None = None) -> Decision:
    session_dir = Path(session_dir)
    session_id = session_dir.name
    bundle = load_bundle(session_dir)
    try:
        integrity = check_integrity(bundle)
    except Exception:
        log.exception("integrity check of %s raised", session_id)
        integrity = [analysis_error("The integrity check did not finish.")]
    if analyze is None:
        analyze, _ = choose_analyze(fake)
    results = integrity + _analyze_with_timeout(analyze, session_dir, timeout_s)
    decision = fuse(results, bundle.plan, int(bundle.session.get("attempt", 1)))
    with store.lock(session_id):
        (session_dir / "results.json").write_text(
            json.dumps([r.model_dump(mode="json") for r in results]), encoding="utf-8"
        )
        (session_dir / "decision.json").write_text(decision.model_dump_json(), encoding="utf-8")
    store.set_state(session_id, "done")
    return decision
