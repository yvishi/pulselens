"""Shared helpers for the engine API tests."""

from __future__ import annotations

import json
from concurrent.futures import Executor, Future

from fastapi.testclient import TestClient

JPEG: bytes = b"\xff\xd8\xff\xd9"
PREFLIGHT: dict = {
    "user_agent": "t", "platform": "desktop", "browser": "b", "camera_label": "c", "width": 640, "height": 480,
    "measured_fps": 30.0, "dropped_frame_ratio": 0.0, "blur": 1.0, "brightness": 120.0, "face_found": True,
    "face_fraction": 0.1, "controls": [], "gyro": False, "no_flash_requested": False, "clock": "now", "probe": [],
}


class SyncExecutor(Executor):
    """Runs each submitted call at once on the caller's thread: /complete returns after the decision is written."""

    def submit(self, fn, /, *args, **kwargs) -> Future:
        future: Future = Future()
        try:
            future.set_result(fn(*args, **kwargs))
        except BaseException as exc:  # noqa: BLE001 - mirror ThreadPoolExecutor: the Future carries the error
            future.set_exception(exc)
        return future


def drive(client: TestClient, *, frames: int = 60, complete: bool = True) -> dict:
    """Walk one session through the customer API: create, preflight, challenge, frames in batches of 20, complete."""
    r = client.post("/api/sessions", json={})
    assert r.status_code == 201, r.text
    created = r.json()
    sid = created["session_id"]
    h = {"Authorization": f"Bearer {created['customer_token']}"}
    r = client.post(f"/api/sessions/{sid}/preflight", headers=h, json=PREFLIGHT)
    assert r.status_code == 200, r.text
    r = client.get(f"/api/sessions/{sid}/challenge", headers=h)
    assert r.status_code == 200, r.text
    for seq, start in enumerate(range(0, frames, 20)):
        idxs = range(start, min(start + 20, frames))
        meta = {"batch_seq": seq, "frames": [{"idx": i, "t_ms": 33.3 * i, "w": 640, "h": 480} for i in idxs]}
        r = client.post(f"/api/sessions/{sid}/frames", headers=h, data={"meta": json.dumps(meta)},
                        files={f"f{i}": (f"{i}.jpg", JPEG, "image/jpeg") for i in idxs})
        assert r.status_code == 204, r.text
    if complete:
        r = client.post(f"/api/sessions/{sid}/complete", headers=h)
        assert r.status_code == 202, r.text
    return created
