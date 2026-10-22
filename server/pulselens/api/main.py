"""FastAPI app: health, the customer session API (K2) and the analysis runner (K4), the agent API (K7)."""

from __future__ import annotations

import functools
from collections.abc import AsyncIterator, Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI

from pulselens.api import agent, sessions
from pulselens.config import Settings, get_settings, load_config
from pulselens.engine.runner import run_analysis
from pulselens.engine.store import Clock, SessionStore, _wall_ms

# run_analysis(session_dir, store): runs after /complete on a worker thread and writes the decision (K4).
Runner = Callable[[Path, SessionStore], Any]


def _default_runner(settings: Settings, config: dict[str, Any]) -> Runner:
    """K4's runner: Ganeev's analyze(), or the fake one when PULSE_FAKE_ANALYSIS=1 (or no analyze exists)."""
    return functools.partial(run_analysis, fake=settings.fake_analysis, timeout_s=config["analysis"]["timeout_s"])


def create_app(
    settings: Settings | None = None,
    *,
    runner: Runner | None = None,
    clock: Clock = _wall_ms,
    config: dict[str, Any] | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    config = config or load_config()
    executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="analysis")

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        executor.shutdown(wait=False, cancel_futures=True)

    app = FastAPI(title="PulseLens", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.config = config
    app.state.store = SessionStore(settings.data_dir, ttl_min=config["session"]["ttl_min"], clock=clock)
    app.state.executor = executor
    app.state.run_analysis = runner or _default_runner(settings, config)

    @app.get("/api/health")
    def health() -> dict[str, bool]:
        return {"ok": True}

    app.include_router(sessions.router)
    app.include_router(agent.router)
    return app


app = create_app()
