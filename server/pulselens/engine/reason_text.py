"""Engine reason codes and their plain sentences (docs/CONTRACT.md section 7).

Prefixes owned here: `mode.`, `integrity.`, `fusion.`, `analysis.`. The agent console shows these sentences; the
customer never sees a reason code.
"""

from __future__ import annotations

REASON_TEXT: dict[str, str] = {
    # mode.* (K3 planner): what the device can do now. Never a risk label.
    "mode.no_flash.requested": "The session runs without flashing light, as requested.",
    "mode.no_flash.too_bright": "The room is too bright for the screen light to matter; the session runs without it.",
    "mode.constrained.fps_too_low_for_light": "The camera is too slow to time the light challenge; only the turn runs.",
    "mode.capable.ok": "The camera, light and face size are good enough for the full challenge.",
    "mode.constrained.fps": "The camera delivers fewer frames than a full challenge needs, so a simpler one runs.",
    "mode.constrained.dim": "The picture is dim, so a simpler, longer challenge runs.",
    "mode.constrained.small_face": "The face is small in the picture, so a simpler, longer challenge runs.",
    "mode.face_not_found": "No face was found before the challenge; the agent should check who is on the call.",
}


def reason_text(code: str) -> str:
    """The sentence for a code, or the code itself when it is unknown (a test keeps the catalogue complete)."""
    return REASON_TEXT.get(code, code)
