"""Fake analysis (docs/tasks/keshav.md K4): one usable, unflagged result for each of B, C and D.

Used when PULSE_FAKE_ANALYSIS=1, or while `pulselens.analysis` has no `analyze`. Every result says so: the console
shows the explanation and a FAKE ANALYSIS label, so a fake PASS is never mistaken for a measurement.
"""

from __future__ import annotations

from pathlib import Path

from pulselens.contracts import CheckResult

EXPLANATION = "FAKE ANALYSIS: not a real measurement."


def analyze(session_dir: Path) -> list[CheckResult]:  # noqa: ARG001 -- same signature as the real analyze
    return [
        CheckResult(
            check_id=f"fake.{family.lower()}", family=family, vote_group=f"{family}.fake", status="usable", risk=0.0,
            flag=False, quality=1.0, explanation=EXPLANATION, window_id="all", threshold_source="provisional",
        )
        for family in ("B", "C", "D")
    ]
