"""Shared synthetic sessions for the analysis tests (Ganeev).

Rendering a session and building its context takes about 2 s, and many tests use the same session. `synth` renders
each distinct set of `make_session` arguments once per test run:
- `synth.session(**kw)` is the bundle path. **Never modify its files**: other tests read them. A test that corrupts
  or copies frames calls `make_session(tmp_path, ...)` itself.
- `synth.context(**kw)` is a deep copy of the built context, so a test may change it freely.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest

from pulselens.analysis.context import AnalysisContext, build_context
from pulselens.analysis.thresholds import Thresholds
from pulselens.bundle import load_bundle
from tests.fixtures.synth import make_session


class Synth:
    def __init__(self, root: Path) -> None:
        self._root = root
        self._paths: dict[tuple, Path] = {}
        self._contexts: dict[tuple, AnalysisContext] = {}

    @staticmethod
    def _key(kw: dict[str, Any]) -> tuple:
        return tuple(sorted(kw.items()))

    def session(self, **kw: Any) -> Path:
        key = self._key(kw)
        if key not in self._paths:
            self._paths[key] = make_session(self._root / f"s{len(self._paths):03d}", **kw)
        return self._paths[key]

    def context(self, **kw: Any) -> AnalysisContext:
        key = self._key(kw)
        if key not in self._contexts:
            self._contexts[key] = build_context(load_bundle(self.session(**kw)), Thresholds.load())
        return copy.deepcopy(self._contexts[key])


@pytest.fixture(scope="session")
def synth(tmp_path_factory: pytest.TempPathFactory) -> Synth:
    return Synth(tmp_path_factory.mktemp("synth"))
