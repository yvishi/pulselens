"""FastAPI app: health, session API (K2), analysis runner (K4), agent API (K7), demo purge (K11)."""

from __future__ import annotations

import asyncio
import contextlib
import functools
from collections.abc import AsyncIterator, Callable
from concurrent.futures import Executor, ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI

from pulselens.api import agent, sessions
from pulselens.config import Settings, get_settings, load_config
from pulselens.engine.purge import purge
from pulselens.engine.runner import run_analysis
from pulselens.engine.store import Clock, SessionStore, _wall_ms

# run_analysis(session_dir, store): runs after /complete on a worker thread and writes the decision (K4).
Runner = Callable[[Path, SessionStore], Any]


def _default_runner(settings: Settings, config: dict[str, Any], pool: ThreadPoolExecutor) -> Runner:
    """K4's runner: Ganeev's analyze(), or the fake one when PULSE_FAKE_ANALYSIS=1 (or no analyze exists)."""
    return functools.partial(run_analysis, pool=pool, fake=settings.fake_analysis,
                             timeout_s=config["analysis"]["timeout_s"])


def create_app(
    settings: Settings | None = None,
    *,
    runner: Runner | None = None,
    clock: Clock = _wall_ms,
    config: dict[str, Any] | None = None,
    executor: Executor | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    config = config or load_config()
    # one runner per completed session; tests pass a synchronous executor
    executor = executor or ThreadPoolExecutor(max_workers=2, thread_name_prefix="analysis")
    analyze_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="analyze")  # analyze() under its timeout

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        async def sweep() -> None:  # demo purge (K11): off the event loop, every 10 minutes after the first sweep
            while True:
                await asyncio.sleep(600)
                await asyncio.to_thread(purge, settings.data_dir, now_ms=clock())

        await asyncio.to_thread(purge, settings.data_dir, now_ms=clock())  # first sweep done before serving
        task = asyncio.create_task(sweep())
        yield
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        executor.shutdown(wait=False, cancel_futures=True)
        analyze_pool.shutdown(wait=False, cancel_futures=True)

    app = FastAPI(title="PulseLens", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.config = config
    app.state.store = SessionStore(
        settings.data_dir,
        ttl_min=config["session"]["ttl_min"],
        clock=clock,
        delete_frames_on_decision=settings.delete_frames_on_decision,
    )
    app.state.executor = executor
    app.state.analyze_pool = analyze_pool
    app.state.runner = runner or _default_runner(settings, config, analyze_pool)

    @app.get("/api/health")
    def health() -> dict[str, bool]:
        return {"ok": True}

    app.include_router(sessions.router)
    app.include_router(agent.router)
    return app


app = create_app()
