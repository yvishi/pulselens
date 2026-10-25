"""Shared contract: every JSON shape on the wire and on disk (docs/CONTRACT.md section 3, verbatim).

Owned by Keshav. Ganeev and Yash read it and never edit it; changes follow docs/PLAN.md section 8.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Mode = Literal["CAPABLE", "CONSTRAINED", "NO_FLASH"]
Family = Literal["A", "B", "C", "D"]          # A pulse, B sensor & stream, C light challenge, D visual & motion
GateStatus = Literal["usable", "abstain", "protocol_error"]
Outcome = Literal["PASS", "RETRY_STEP_UP", "HUMAN_REVIEW"]
StepUp = Literal["fresh_challenge", "no_flash", "agent_checks", "assisted_kyc"]
SessionState = Literal["created", "preflight", "capturing", "analysing", "done", "expired"]
CustomerMessage = Literal["please_wait", "continue", "please_retry", "assisted_route"]
AgentAction = Literal["approve", "reverify", "escalate"]
Product = Literal["savings_account", "instant_loan"]
Platform = Literal["android", "ios", "desktop", "unknown"]
FamilyState = Literal["flag", "not_raised", "abstained", "not_run"]
ThresholdSource = Literal["provisional", "calibrated", "rule"]
PlotKind = Literal["echo", "turn", "cadence", "bars"]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Label(Model):
    """Lab recordings only. Pseudonymous codes; never names."""
    person: str = Field(pattern=r"^P\d{2}$")
    device: str = Field(pattern=r"^D\d{2}$")
    light: Literal["bright", "normal", "dim", "tube"]
    kind: Literal["genuine", "replay_screen", "virtual_camera", "live_swap", "photo_animation"]
    tool: str | None = None          # "obs", "deep_live_cam", "facefusion", "liveportrait", "phone_screen"
    set: Literal["A", "B"]           # A = tuning/calibration, B = held-out evaluation
    consent_ref: str


class SessionCreate(Model):
    product: Product = "savings_account"
    no_flash: bool = False
    label: Label | None = None
    previous_session_id: str | None = None


class SessionCreated(Model):
    session_id: str                  # secrets.token_hex(8)
    nonce: str                       # secrets.token_hex(16); bound into the challenge, single use
    customer_token: str
    customer_url: str                # "/customer/{session_id}?t={customer_token}"
    attempt: int
    expires_at_ms: int


class ModeProbe(Model):
    requested: tuple[int, int, int]  # width, height, fps asked for
    accepted: bool
    delivered: tuple[int, int] | None
    switch_ms: float | None          # from applyConstraints() to the first frame at the new size
    frames_missing: int | None       # frames expected at the old rate but not delivered during the switch


class Preflight(Model):
    user_agent: str
    platform: Platform
    browser: str
    camera_label: str
    width: int
    height: int
    measured_fps: float              # median over >= 2 s
    dropped_frame_ratio: float       # 0..1
    blur: float                      # variance of the Laplacian of luma on a 160x120 downscale
    brightness: float                # mean luma 0..255
    face_found: bool
    face_fraction: float             # face box area / frame area, 0..1
    controls: list[str]              # from track.getCapabilities(), e.g. ["exposureMode", "whiteBalanceMode", "torch"]
    gyro: bool
    no_flash_requested: bool
    clock: Literal["captureTime", "expectedDisplayTime", "now"]
    probe: list[ModeProbe]


class Plan(Model):
    mode: Mode
    run_light: bool
    run_turn: bool
    agent_questions: bool
    reasons: list[str]               # reason codes, see docs/CONTRACT.md section 7


class ColourStep(Model):
    kind: Literal["colour"] = "colour"
    step_id: str                     # "c0", "c1", ...
    hue_deg: int                     # never in [345, 360) or [0, 15]: no saturated red
    start_offset_ms: int             # from the end of the baseline
    dwell_ms: int


class TurnStep(Model):
    kind: Literal["turn"] = "turn"
    step_id: str                     # "t0"
    direction: Literal["left", "right"]   # the person's own left/right
    start_offset_ms: int
    duration_ms: int


class PulseHoldStep(Model):
    """Neutral-screen steady hold. Dormant until planner and capture integration."""

    kind: Literal["pulse_hold"] = "pulse_hold"
    step_id: str
    start_offset_ms: int = Field(ge=0)  # from the end of the baseline
    duration_ms: int = Field(gt=0)


Step = Annotated[ColourStep | TurnStep, Field(discriminator="kind")]


class Challenge(Model):
    session_id: str
    nonce: str
    mode: Mode
    baseline_ms: int                 # neutral screen before the first step
    steps: list[Step]                # sorted by start_offset_ms
    total_ms: int


class FrameMeta(Model):
    idx: int                         # 0, 1, 2 ... strictly increasing per session
    t_ms: float                      # ms since t0
    w: int
    h: int


class FrameBatchMeta(Model):
    batch_seq: int                   # 0, 1, 2 ...
    frames: list[FrameMeta]


class ChallengeEvent(Model):
    step_id: str
    status: Literal["shown", "skipped"]
    painted_t_ms: float | None       # first rAF after the colour/prompt was committed (double rAF)
    ended_t_ms: float | None
    shown_rgb: tuple[float, float, float] | None   # colour steps: the sRGB actually painted
    skip_reason: str | None = None   # "fps_drop", "no_flash", "page_hidden"


class Plot(Model):
    kind: PlotKind
    series: dict[str, list[tuple[float, float]]]   # name -> [(t_ms, value)], <= 300 points each
    markers: list[tuple[float, str]] = []          # (t_ms, label), e.g. step starts
    # NEVER a pulse waveform or a heart rate (family A plots are not allowed).


class CheckResult(Model):
    check_id: str                    # "<area>.<name>", e.g. "light.response"; integrity.* belongs to the engine
    family: Family
    vote_group: str                  # correlated cues share one vote, e.g. "B.stream"
    status: GateStatus
    risk: float | None               # 0..1, higher = more suspicious; None unless status == "usable"
    flag: bool                       # True only when status == "usable" and risk >= the check's threshold
    quality: float                   # 0..1
    uncertainty: float | None = None
    features: dict[str, float] = {}
    reason_codes: list[str] = []
    explanation: str                 # one plain sentence for the agent, with real numbers
    window_id: str | None = None     # "c2", "t0", "all"
    threshold_source: ThresholdSource
    plot: Plot | None = None
    voting: bool = True              # False: measured, not voting (never flags), so it covers no family in fusion


class FamilySummary(Model):
    family: Family
    state: FamilyState
    usable_checks: int
    flagged_checks: int
    reasons: list[str]               # plain sentences


class Decision(Model):
    outcome: Outcome
    step_up: StepUp | None
    families: list[FamilySummary]    # always A, B, C, D in that order
    reasons: list[str]               # plain sentences, most important first
    integrity_violation: bool
    provisional: bool                # True while any result used threshold_source "provisional"
    decided_at_ms: int


class CustomerStatus(Model):
    state: SessionState
    message: CustomerMessage


class AgentDecision(Model):
    action: AgentAction
    note: str = ""
    at_ms: int | None = None  # set by the engine when it records the action; clients leave it out


class SessionSummary(Model):
    session_id: str
    created_at_ms: int
    product: Product
    attempt: int
    state: SessionState
    mode: Mode | None
    outcome: Outcome | None
    label_kind: str | None
    agent_action: AgentAction | None = None  # the agent's last action, if any


class SessionReport(Model):
    session_id: str
    product: Product
    attempt: int
    state: SessionState
    label: Label | None
    preflight: Preflight | None
    plan: Plan | None
    challenge: Challenge | None
    events: list[ChallengeEvent]
    frame_count: int
    results: list[CheckResult]
    decision: Decision | None
    agent_decision: AgentDecision | None
