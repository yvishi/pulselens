"""FastAPI app. Routes arrive with K2 (sessions) and K7 (agent)."""

from __future__ import annotations

from fastapi import FastAPI

from pulselens.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(title="PulseLens", version="0.1.0")
    app.state.settings = settings or get_settings()

    @app.get("/api/health")
    def health() -> dict[str, bool]:
        return {"ok": True}

    return app


app = create_app()
