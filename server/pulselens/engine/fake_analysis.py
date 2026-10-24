"""Fake analysis (docs/tasks/keshav.md K4): one usable, unflagged result for each of B, C and D.
D's result carries the turn challenge's id (`turn.follow`), because fusion only passes a session whose live challenge
was verified (CONTRACT section 8, row 6).

Used when PULSE_FAKE_ANALYSIS=1, or while `pulselens.analysis` has no `analyze`. Every result says so: the console
shows the explanation and a FAKE ANALYSIS label, so a fake PASS is never mistaken for a measurement.
"""

from __future__ import annotations

from pathlib import Path

from pulselens.contracts import CheckResult
from pulselens.engine.results import usable

EXPLANATION = "FAKE ANALYSIS: not a real measurement."


def analyze(session_dir: Path) -> list[CheckResult]:  # noqa: ARG001 -- same signature as the real analyze
    ids = {"B": "fake.b", "C": "fake.c", "D": "turn.follow"}
    return [usable(ids[f], EXPLANATION, family=f, vote_group=f"{f}.fake", source="provisional")
            for f in ("B", "C", "D")]
