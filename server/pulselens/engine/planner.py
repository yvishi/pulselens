"""Planner and challenge (service step 1; docs/tasks/keshav.md K3). Pure functions: no I/O, no clock.

The capture mode says what this device can do right now. It is never a risk label: nothing downstream may treat
CONSTRAINED or NO_FLASH as suspicious.
"""

from __future__ import annotations

import hashlib
import random
from typing import Any

from pulselens.contracts import Challenge, ColourStep, Plan, Preflight, TurnStep

# Every reason code plan_session can emit (each has a sentence in reason_text.py).
MODE_REASONS = (
    "mode.no_flash.requested",
    "mode.no_flash.too_bright",
    "mode.constrained.fps_too_low_for_light",
    "mode.capable.ok",
    "mode.constrained.fps",
    "mode.constrained.dim",
    "mode.constrained.small_face",
    "mode.face_not_found",
)

TAIL_MS = 1500  # after the last step, before the challenge ends: a slow head is back from the turn (S2, 2026-10-24)


def plan_session(pre: Preflight, session_no_flash: bool, cfg: dict[str, Any]) -> Plan:
    """The first matching rule wins (K3 rules 1 to 5)."""
    p = cfg["planner"]
    lo, hi = p["brightness_range"]
    fps, brightness, face = pre.measured_fps, pre.brightness, pre.face_fraction

    if session_no_flash or pre.no_flash_requested:
        plan = Plan(mode="NO_FLASH", run_light=False, run_turn=True, agent_questions=True,
                    reasons=["mode.no_flash.requested"])
    elif brightness > hi:
        plan = Plan(mode="NO_FLASH", run_light=False, run_turn=True, agent_questions=True,
                    reasons=["mode.no_flash.too_bright"])
    elif fps < p["light_min_fps"]:
        plan = Plan(mode="CONSTRAINED", run_light=False, run_turn=True, agent_questions=True,
                    reasons=["mode.constrained.fps_too_low_for_light"])
    elif fps >= p["capable_min_fps"] and lo <= brightness <= hi and face >= p["min_face_fraction"]:
        plan = Plan(mode="CAPABLE", run_light=True, run_turn=True, agent_questions=False, reasons=["mode.capable.ok"])
    else:
        failed = []
        if fps < p["capable_min_fps"]:
            failed.append("mode.constrained.fps")
        if brightness < lo:
            failed.append("mode.constrained.dim")
        if face < p["min_face_fraction"]:
            failed.append("mode.constrained.small_face")
        plan = Plan(mode="CONSTRAINED", run_light=True, run_turn=True, agent_questions=False, reasons=failed)

    if not pre.face_found:
        plan.reasons.append("mode.face_not_found")
        plan.agent_questions = True
    return plan


def rng_for_nonce(nonce: str) -> random.Random:
    """Reproducible per session (same nonce, same challenge), unpredictable across sessions."""
    return random.Random(int.from_bytes(hashlib.sha256(nonce.encode()).digest()[:8], "big"))


def make_challenge(plan: Plan, session_id: str, nonce: str, rng: random.Random, cfg: dict[str, Any]) -> Challenge:
    c = cfg["challenge"]
    mode_cfg = c[plan.mode.lower()]
    steps: list[ColourStep | TurnStep] = []
    end = 0  # end of the last step, ms after the baseline

    if plan.run_light and plan.mode != "NO_FLASH":
        n = int(mode_cfg["colour_steps"])
        hues = rng.sample(list(c["hues_deg"]), n)  # without replacement, in random order
        gap_lo, gap_hi = mode_cfg["gap_ms"]
        dwell = int(mode_cfg["dwell_ms"])
        for k, hue in enumerate(hues):
            start = 0 if k == 0 else end + rng.randint(int(gap_lo), int(gap_hi))
            steps.append(ColourStep(step_id=f"c{k}", hue_deg=int(hue), start_offset_ms=start, dwell_ms=dwell))
            end = start + dwell

    if plan.run_turn:
        start = end + int(c["turn_gap_ms"]) if steps else 0
        duration = int(mode_cfg["turn_ms"])
        steps.append(TurnStep(step_id="t0", direction=rng.choice(["left", "right"]), start_offset_ms=start,
                              duration_ms=duration))
        end = start + duration

    return Challenge(session_id=session_id, nonce=nonce, mode=plan.mode, baseline_ms=int(c["baseline_ms"]),
                     steps=steps, total_ms=end + TAIL_MS)
