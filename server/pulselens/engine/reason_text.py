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
    # integrity.* (K5): the capture protocol and the upload.
    "integrity.non_monotonic_time": "Frame times did not increase with the frame number.",
    "integrity.duplicate_index": "The same frame number was uploaded more than once.",
    "integrity.unknown_step": "An event named a challenge step that was never issued.",
    "integrity.event_order": "The challenge steps were shown out of the order they were issued in.",
    "integrity.after_complete": "Frames or events were sent after the session was completed.",
    "integrity.no_challenge": "Frames arrived although no challenge was ever issued.",
    "integrity.too_few_frames": "Too few frames arrived to judge the upload.",
    "integrity.batch_gaps": "Too many upload batches went missing to rely on the recording.",
    # analysis.* (K4): the runner itself.
    "analysis.error": "The analysis did not finish, so its checks could not judge this session.",
    # fusion.* (K6): the outcome sentence, first in Decision.reasons.
    "fusion.integrity_violation": "The session broke the capture protocol, so a person must review it.",
    "fusion.two_families": "Two independent kinds of evidence raised risk, so a person must review it.",
    "fusion.one_family": "One kind of evidence raised risk; a further check is needed before deciding.",
    "fusion.low_coverage": "Too little usable evidence was captured to decide; a further check is needed.",
    "fusion.challenge_not_done": "A live prompt (head turn, nod or digits read aloud) was shown but not performed, "
                                 "so the live challenge is repeated.",
    "fusion.liveness_not_shown": "The live challenge could not be verified, so a further check is needed.",
    "fusion.pass": "The live challenge was verified, enough usable evidence was captured and none of it raised risk.",
    "fusion.step_up.fresh_challenge": "Suggested next step: run a fresh challenge.",
    "fusion.step_up.no_flash": "Suggested next step: repeat without the flashing light.",
    "fusion.step_up.agent_checks": "Suggested next step: the agent asks live questions and checks.",
    "fusion.step_up.assisted_kyc": "Suggested next step: move to assisted KYC (branch or correspondent).",
}


def reason_text(code: str) -> str:
    """The sentence for a code, or the code itself when it is unknown (a test keeps the catalogue complete)."""
    return REASON_TEXT.get(code, code)
