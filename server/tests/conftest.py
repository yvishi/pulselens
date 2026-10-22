"""Shared fixtures (Keshav). Tests never touch data/sessions: every app gets a tmp data dir and a known passcode."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pulselens.api.main import create_app
from pulselens.config import Settings

PASSCODE = "test-passcode"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(agent_passcode=PASSCODE, data_dir=tmp_path / "data", fake_analysis=True)


@pytest.fixture
def client(settings: Settings) -> TestClient:
    with TestClient(create_app(settings)) as c:
        yield c
