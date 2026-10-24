"""Reason code -> one plain English sentence, for every code the analysis emits (CONTRACT section 7).

Prefixes owned here: quality., sensor., light., turn., visual., pulse. A test fails if an emitted code is missing.
"""

from __future__ import annotations

PREFIXES = ("quality.", "sensor.", "light.", "turn.", "visual.", "pulse.")

REASON_TEXT: dict[str, str] = {
    # quality gate (G1, G2)
    "quality.no_frames": "No readable video frames reached the analysis.",
    "quality.check_error": "This check could not be measured on this session.",
    "quality.low_fps": "The camera delivered too few frames per second to time the response.",
    "quality.no_face": "The face was not visible in enough of the video.",
    "quality.too_dark": "The face was too dark to measure.",
    "quality.too_bright": "The face was too bright to measure.",
    "quality.neck_hidden": "The neck was not visible enough to compare with the face.",
    "quality.moving": "The face moved too much to measure.",
    "quality.clipped": "Parts of the face or neck were overexposed.",
    "quality.frames_missing": "Some video frames were lost on the way to the server; that gap is not held against "
                              "the camera.",
    "quality.page_hidden": "The page was in the background for a while, so no video arrived then.",
    "quality.too_few_frames": "Too few usable video frames for this measurement.",
    "quality.heavy_compression": "The video was compressed too heavily to measure the camera's noise.",
    # family B: sensor and stream (G4, G8)
    "sensor.stall": "The video stopped for more than a second.",
    "sensor.too_regular": "Frames arrived on a perfectly regular clock, unlike a physical camera.",
    "sensor.duplicates": "Many frames were near-identical repeats.",
    "sensor.probe_too_perfect": "The camera switched to an unusual mode instantly and without losing a frame.",
    "sensor.probe_not_run": "The camera mode probe did not run or no mode was accepted (unsupported, not failed).",
    "sensor.phantom_switch": "The camera reported a new size but the delivered frames did not change.",
    "sensor.regions_mismatch": "The face's noise or sharpness differed from the neck and background.",
    "sensor.prnu_weak": "No stable sensor noise pattern was found (supporting evidence only).",
    # family C: light challenge (G3, G5)
    "light.too_few_steps": "Too few colour steps were usable to judge the light response.",
    "light.no_echo": "The face did not answer the screen colours.",
    "light.wrong_order": "The face's colour response did not match the colours shown.",
    "light.neck_only": "The neck answered the screen light while the face did not.",
    "light.ratio": "The face and neck answered the light with very different strengths.",
    "light.background_even": "The background answered the light as strongly as the face.",
    "light.weak_face_echo": "The face's response to the light was too weak to compare.",
    "light.weak_echoes": "The face and neck responses were too close to the noise to compare.",
    "light.background_hidden": "Too little of the background was visible to compare with the face.",
    # family D: turn and visual (G6, G7, G10)
    "turn.not_performed": "The head turn was not performed.",
    "turn.wrong_direction": "The head turned the opposite way to the prompt.",
    "turn.face_lost": "The face was lost during the head turn.",
    "turn.no_return": "The head turned as asked but had not come back by the end (noted, not scored).",
    "turn.too_fast": "The head turn started unusually fast after the prompt (measured, not scored).",
    "turn.no_frontal": "There were no frontal frames on both sides of the turn.",
    "turn.identity_change": "The face's proportions changed through the turn.",
    "visual.model_missing": "The SBI detector weights are not installed.",
    "visual.sbi_high": "The deepfake detector scored the face as likely manipulated.",
    "visual.edge_flicker_high": "The edge of the face changed more from frame to frame than its middle "
                                "(measured, not scored).",
    # family A: pulse (G10, logged only)
    "pulse.not_measured": "Pulse coherence needs steady, well-lit video at 20 fps or more.",
}


def reason_text(code: str) -> str:
    return REASON_TEXT.get(code, code)
