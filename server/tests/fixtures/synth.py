"""Synthetic session bundles (no real faces, no face model, no network). Ported from the old repo's light model.

Light model: each region reflects ambient light plus the screen, `rgb(t) = albedo * (ambient + k * screen(t - delay))`,
where the screen is a neutral grey between colour steps and the step's colour while it is painted. A frame's value is
the average over its exposure (the frame interval before its time), so an echo onset falls between frames as on a
real sensor. Pixels get Gaussian sensor noise and each region a small per-frame illumination jitter.

Kinds (what the evidence checks must tell apart; signal patterns only, nothing here makes a fake face):
- genuine: face and neck answer the screen together, `delay_ms` after each step is painted
- replay: neither answers (the face is a recording that never saw this screen)
- swap_no_face_echo: the neck answers, the face does not (a face pasted over a real person)
- virtual_camera: no echo, a perfect frame clock and zero sensor noise
"""

from __future__ import annotations

import colorsys
import json
from pathlib import Path
from typing import Literal

import cv2
import numpy as np

from pulselens.analysis.landmarks import write_cache
from pulselens.analysis.vision.linearize import linear_to_srgb, srgb_to_linear
from pulselens.bundle import write_bundle
from pulselens.config import load_config
from pulselens.contracts import (
    Challenge,
    ChallengeEvent,
    ColourStep,
    FrameMeta,
    Label,
    Plan,
    Preflight,
    TurnStep,
)

Kind = Literal["genuine", "replay", "swap_no_face_echo", "virtual_camera"]

W, H = 320, 240
LUMA = np.array([0.2126, 0.7152, 0.0722])
NEUTRAL_Y = 0.5  # linear luminance of the neutral screen and of every colour step
SKIN = np.array([0.42, 0.27, 0.20])  # linear albedo-ish values; only ratios matter
SHIRT = np.array([0.30, 0.32, 0.38])
WALL = np.array([0.35, 0.35, 0.33])
AMBIENT, K = 0.5, 0.35
PAINT_LAG_MS = 16.0  # from the step's scheduled start to the first painted frame
TURN_DEG = 30.0
_ENCODE_STEPS = 4096  # linear -> sRGB uint8 through a lookup table (pow on every pixel is the slow part)
_ENCODE = np.round(linear_to_srgb(np.linspace(0, 1, _ENCODE_STEPS)) * 255).astype(np.uint8)
_BANK_FIELDS, _BANK_PAD = 16, 32
_bank: np.ndarray | None = None


def _noise_field(rng: np.random.Generator) -> np.ndarray:
    """A unit Gaussian (H, W, 3) noise field: a random crop of a fixed bank, so frames get different noise without
    drawing 230k normals each (16 x 33 x 33 distinct fields; consecutive frames practically never share one)."""
    global _bank
    if _bank is None:
        _bank = np.random.default_rng(12345).standard_normal(
            (_BANK_FIELDS, H + _BANK_PAD, W + _BANK_PAD, 3), dtype=np.float32)
    k, dy, dx = rng.integers(0, _BANK_FIELDS), rng.integers(0, _BANK_PAD + 1), rng.integers(0, _BANK_PAD + 1)
    return _bank[k, dy:dy + H, dx:dx + W]

LABEL_KIND = {"genuine": "genuine", "replay": "replay_screen", "swap_no_face_echo": "live_swap",
              "virtual_camera": "virtual_camera"}


def isoluminant(hue_deg: float, y: float = NEUTRAL_Y) -> tuple[float, float, float]:
    """sRGB 0..1 of a hue at linear luminance `y` (an approximation of Yash's isoluminantColour)."""
    lin = srgb_to_linear(np.array(colorsys.hsv_to_rgb((hue_deg % 360) / 360, 0.6, 1.0)))
    lin = np.clip(lin * y / float(lin @ LUMA), 0, 1)
    return tuple(float(v) for v in linear_to_srgb(lin))


NEUTRAL_SRGB = tuple(float(v) for v in linear_to_srgb(np.full(3, NEUTRAL_Y)))


def synthetic_landmarks(chin_y: float = 150.0) -> dict[int, tuple[float, float]]:
    """Pixel landmarks of a frontal face box 80 wide, 110 tall, chin at `chin_y`, centred at x = 160."""
    top = chin_y - 110
    cx, mid = 160.0, chin_y - 55
    return {
        10: (cx, top), 152: (cx, chin_y), 234: (120, mid), 454: (200, mid),
        70: (128, top + 25), 105: (140, top + 22), 66: (146, top + 21), 107: (152, top + 22), 63: (134, top + 23),
        300: (192, top + 25), 334: (180, top + 22), 296: (174, top + 21), 336: (168, top + 22), 293: (186, top + 23),
        145: (140, top + 44), 374: (180, top + 44),
        50: (138, top + 66), 280: (182, top + 66),
        13: (cx, top + 88), 14: (cx, top + 92),
    }


def landmarks_478(chin_y: float = 150.0) -> list[list[float]]:
    """All 478 landmarks, normalised, as landmarks.jsonl stores them. The unused ones sit at the face centre."""
    used = synthetic_landmarks(chin_y)
    centre = (160.0, chin_y - 55)
    return [[used.get(i, centre)[0] / W, used.get(i, centre)[1] / H, 0.0] for i in range(478)]


def make_challenge(session_id: str, nonce: str, *, n_colour: int, turn: Literal["left", "right"] | None,
                   rng: np.random.Generator) -> Challenge:
    c = load_config()["challenge"]
    mode = c["capable"]
    steps: list[ColourStep | TurnStep] = []
    end = 0
    for k, hue in enumerate(list(c["hues_deg"])[:n_colour]):
        start = 0 if k == 0 else end + int(rng.integers(mode["gap_ms"][0], mode["gap_ms"][1] + 1))
        steps.append(ColourStep(step_id=f"c{k}", hue_deg=int(hue), start_offset_ms=start, dwell_ms=mode["dwell_ms"]))
        end = start + mode["dwell_ms"]
    if turn is not None:
        start = end + c["turn_gap_ms"] if steps else 0
        steps.append(TurnStep(step_id="t0", direction=turn, start_offset_ms=start, duration_ms=mode["turn_ms"]))
        end = start + mode["turn_ms"]
    return Challenge(session_id=session_id, nonce=nonce, mode="CAPABLE", baseline_ms=c["baseline_ms"], steps=steps,
                     total_ms=end + 500)


def challenge_events(ch: Challenge) -> list[ChallengeEvent]:
    out = []
    for s in ch.steps:
        painted = ch.baseline_ms + s.start_offset_ms + PAINT_LAG_MS
        if isinstance(s, ColourStep):
            out.append(ChallengeEvent(step_id=s.step_id, status="shown", painted_t_ms=painted,
                                      ended_t_ms=painted + s.dwell_ms, shown_rgb=isoluminant(s.hue_deg)))
        else:
            out.append(ChallengeEvent(step_id=s.step_id, status="shown", painted_t_ms=painted,
                                      ended_t_ms=painted + s.duration_ms, shown_rgb=None))
    return out


def _light(t: np.ndarray, exposure: float, events: list[ChallengeEvent], delay: float, k: float,
           colours: list[tuple[float, float, float]] | None = None) -> np.ndarray:
    """(n, 3) exposure-averaged screen + ambient light reaching a region. `colours` (sRGB, one per colour event)
    overrides what each step lit the region with; default: the colour the event says was shown."""
    neutral = srgb_to_linear(np.array(NEUTRAL_SRGB))
    light = np.tile(AMBIENT + k * neutral, (len(t), 1))
    shown = [e for e in events if e.shown_rgb is not None]
    for e, rgb in zip(shown, colours or [e.shown_rgb for e in shown], strict=True):
        a, b = e.painted_t_ms + delay, e.ended_t_ms + delay
        overlap = np.clip(np.minimum(t, b) - np.maximum(t - exposure, a), 0, None) / exposure
        light += overlap[:, None] * k * (srgb_to_linear(np.array(rgb)) - neutral)
    return light


def _turn_event(ch: Challenge, events: list[ChallengeEvent]) -> ChallengeEvent | None:
    turn = next((s for s in ch.steps if isinstance(s, TurnStep)), None)
    return next((e for e in events if turn is not None and e.step_id == turn.step_id), None)


def _yaw(t: np.ndarray, events: list[ChallengeEvent], ch: Challenge, followed: bool, *, performed: str | None,
         start_ms: float, returns: bool) -> np.ndarray:
    """Head yaw: still, then (when followed) out to 30 degrees and, if `returns`, back before the step ends.
    `performed` is the direction actually turned (default: the one requested)."""
    yaw = np.zeros(len(t))
    turn = next((s for s in ch.steps if isinstance(s, TurnStep)), None)
    ev = _turn_event(ch, events)
    if turn is None or ev is None or not followed:
        return yaw
    sign = 1.0 if (performed or turn.direction) == "left" else -1.0  # CONTRACT section 1: + = the person's own left
    up0, up1 = ev.painted_t_ms + start_ms, ev.painted_t_ms + start_ms + 400
    down0, down1 = ev.ended_t_ms - 800, ev.ended_t_ms - 400
    ramp = np.clip((t - up0) / (up1 - up0), 0, 1)
    if returns:
        ramp = ramp - np.clip((t - down0) / (down1 - down0), 0, 1)
    return sign * TURN_DEG * ramp


def make_session(
    root: Path,
    *,
    kind: Kind = "genuine",
    fps: float = 30.0,
    n_colour: int = 6,
    turn: Literal["left", "right"] | None = "left",
    turn_followed: bool = True,
    noise: float = 0.003,
    seed: int = 0,
    delay_ms: float = 100.0,
    chin_y: float = 150.0,
    face_in_frames: bool = True,
    swap_colours: bool = False,
    neck_gain: float = 1.0,
    face_noise_gain: float = 1.0,
    background_echo: float = 0.05,
    turn_performed: Literal["left", "right"] | None = None,
    turn_start_ms: float = 300.0,
    turn_returns: bool = True,
    face_lost_in_turn: float = 0.0,
) -> Path:
    """Writes a complete bundle (bundle.write_bundle) plus landmarks.jsonl under `root` and returns its path.

    `swap_colours`: the face and neck answer with the colour of the step half a sequence away (a recording of another
    session's challenge), while events.jsonl records what this session painted.
    `neck_gain`: how strongly the neck (or shirt) answers the screen relative to the face, as a darker or shinier
    shirt does. `face_noise_gain`: extra per-frame illumination jitter on the face only. `background_echo`: the
    wall's share of the screen light (a glossy replay screen filling the frame answers evenly, near 1).
    Turn: `turn_performed` is the direction actually turned, `turn_start_ms` the reaction time after the prompt,
    `turn_returns` whether the head comes back, `face_lost_in_turn` the share of the turn window (painted to
    ended + 500 ms) at its peak where no face is found."""
    rng = np.random.default_rng(seed)
    session_id = f"synth{seed:03d}{kind[:4]}"
    path = Path(root) / session_id
    ch = make_challenge(session_id, f"{seed:032x}", n_colour=n_colour, turn=turn, rng=rng)
    events = challenge_events(ch)

    perfect = kind == "virtual_camera"
    noise = 0.0 if perfect else noise
    interval = 1000.0 / fps
    t = np.arange(0, ch.baseline_ms + ch.total_ms, interval)
    if not perfect:
        t = np.sort(t + rng.normal(0, 1.0, len(t)))
        t = t - t[0]

    face_k = K if kind == "genuine" else 0.0
    neck_k = K * neck_gain if kind in ("genuine", "swap_no_face_echo") else 0.0
    lit = [e.shown_rgb for e in events if e.shown_rgb is not None]
    lit = [lit[(k + len(lit) // 2) % len(lit)] for k in range(len(lit))] if swap_colours and lit else None
    face = _light(t, interval, events, delay_ms, face_k, lit) * SKIN
    neck = _light(t, interval, events, delay_ms, neck_k, lit) * SHIRT
    wall = _light(t, interval, events, delay_ms, background_echo * K) * WALL
    yaw = _yaw(t, events, ch, turn_followed, performed=turn_performed, start_ms=turn_start_ms,
               returns=turn_returns) + (0 if perfect else rng.normal(0, 0.5, len(t)))
    lost = np.zeros(len(t), dtype=bool)
    ev = _turn_event(ch, events)
    if face_lost_in_turn > 0 and ev is not None:
        w0, w1 = ev.painted_t_ms, ev.ended_t_ms + 500
        mid, half = (w0 + w1) / 2, face_lost_in_turn * (w1 - w0) / 2
        lost = (t >= mid - half) & (t <= mid + half)

    fx0, fy0, fx1, fy1 = 120, int(chin_y - 110), 200, int(chin_y)
    frames, lms = [], {}
    lm = landmarks_478(chin_y)
    for i, ti in enumerate(t):
        img = np.empty((H, W, 3), dtype=np.float32)
        img[:] = wall[i] + rng.normal(0, noise / 5, 3) if noise else wall[i]
        if face_in_frames:
            img[fy1:H, 130:190] = neck[i] + (rng.normal(0, noise / 5, 3) if noise else 0)
            img[fy0:fy1, fx0:fx1] = face[i] + (rng.normal(0, face_noise_gain * noise / 5, 3) if noise else 0)
        if noise:
            img += _noise_field(rng) * np.float32(noise)
        srgb = _ENCODE[np.clip(img * (_ENCODE_STEPS - 1) + 0.5, 0, _ENCODE_STEPS - 1).astype(np.int32)]
        ok, jpeg = cv2.imencode(".jpg", cv2.cvtColor(srgb, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 95])
        assert ok
        frames.append((FrameMeta(idx=i, t_ms=float(ti), w=W, h=H), jpeg.tobytes()))
        lms[i] = {"landmarks": lm, "yaw": float(yaw[i]), "pitch": 0.0} if face_in_frames and not lost[i] else None

    label = Label(person="P00", device="D00", light="normal", kind=LABEL_KIND[kind], set="A", consent_ref="synthetic")
    session = {"session_id": session_id, "nonce": ch.nonce, "product": "savings_account", "no_flash": False,
               "attempt": 1, "previous_session_id": None, "created_at_ms": 0, "expires_at_ms": 900_000,
               "state": "analysing", "label": json.loads(label.model_dump_json()), "synthetic": True}
    preflight = Preflight(user_agent="synthetic", platform="desktop", browser="synthetic", camera_label="synthetic",
                          width=W, height=H, measured_fps=fps, dropped_frame_ratio=0.0, blur=100.0, brightness=150.0,
                          face_found=face_in_frames, face_fraction=0.11, controls=[], gyro=False,
                          no_flash_requested=False, clock="captureTime", probe=[])
    plan = Plan(mode="CAPABLE", run_light=n_colour > 0, run_turn=turn is not None, agent_questions=False,
                reasons=["mode.capable.ok"])
    write_bundle(path, session=session, preflight=preflight, plan=plan, challenge=ch, frames=frames, events=events)
    write_cache(path, lms)
    return path
