"""Shared helpers for the engine API tests."""

from __future__ import annotations

from concurrent.futures import Executor, Future


class SyncExecutor(Executor):
    """Runs each submitted call at once on the caller's thread: /complete returns after the decision is written."""

    def submit(self, fn, /, *args, **kwargs) -> Future:
        future: Future = Future()
        try:
            future.set_result(fn(*args, **kwargs))
        except BaseException as exc:  # noqa: BLE001 - mirror ThreadPoolExecutor: the Future carries the error
            future.set_exception(exc)
        return future
