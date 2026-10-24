# Shared contract

Everything in this file is shared by all three owners. It is the only coupling between the three task lists:
if each person builds to this file, the pieces fit without anyone editing anyone else's files.

- **Owner of the code that implements this file:** Keshav (`server/pulselens/contracts.py`, `server/pulselens/bundle.py`, `web/src/contracts.ts`, `web/src/api/client.ts`).
- **Changing it:** see "Contract changes" in `docs/PLAN.md`. Additive optional fields are allowed at any time by Keshav, with a GitHub issue to the others. Anything else waits for a sync point and needs all three to agree.
- **JSON naming:** `snake_case` everywhere, in Python, TypeScript and on the wire. Do not camelCase in TS.

---

## 1. Clocks and units

- **Client time** is `performance.now()` in milliseconds. `t0` = `performance.now()` when the challenge starts (the first baseline frame). Every client time on the wire is **ms since t0** (`t_ms`, `painted_t_ms`, `ended_t_ms`). Never use `Date.now()` for these.
- **Frame time** is the requestVideoFrameCallback `metadata.captureTime` when present, else `metadata.expectedDisplayTime`, else the callback's `now`. All three are in the `performance.now()` domain; subtract `t0`.
- **Server time** is `time.time()` in ms (`*_at_ms`). Server time is never compared with client time.
- **Colours** on the wire are sRGB in 0..1.
- **Angles** are degrees. Yaw is positive when the person turns to **their own left** (the camera sees the face turn to image-right).

---

## 2. REST API (FastAPI, prefix `/api`)

Auth:
- **Customer endpoints:** header `Authorization: Bearer <customer_token>`.
- **Agent endpoints:** header `X-Agent-Passcode: <AGENT_PASSCODE from .env>`.
- Wrong or missing auth → 401 `{"detail": "unauthorized"}`.
- Unknown session → 404. A session expires 15 min after it is created; after that every customer call → 410.

| # | Method and path | Auth | Request body | Response | Errors |
|---|---|---|---|---|---|
| 1 | `GET /api/health` | none | — | `{"ok": true}` | — |
| 2 | `POST /api/sessions` | none | `SessionCreate` | `SessionCreated` (201) | 422 |
| 3 | `POST /api/sessions/{id}/preflight` | customer | `Preflight` | `Plan` | 409 if the challenge was already issued |
| 4 | `GET /api/sessions/{id}/challenge` | customer | — | `Challenge` | 409 `challenge_already_issued` on the 2nd call (single use); 409 `no_plan` before preflight |
| 5 | `POST /api/sessions/{id}/frames` | customer | multipart: part `meta` = `FrameBatchMeta` JSON; parts `f{idx}` = `image/jpeg`, one per frame in `meta.frames` | 204 | 409 after complete; 413 if a batch has > 30 frames, a JPEG is > 200 KB, or the session would exceed 900 frames |
| 6 | `POST /api/sessions/{id}/events` | customer | `list[ChallengeEvent]` | 204 | 409 after complete |
| 7 | `POST /api/sessions/{id}/complete` | customer | — | 202; analysis runs in the background | 409 if already complete |
| 8 | `GET /api/sessions/{id}/status` | customer | — | `CustomerStatus` | — |
| 9 | `GET /api/sessions` | agent | — | `list[SessionSummary]`, newest first | — |
| 10 | `GET /api/sessions/{id}/result` | agent | — | `SessionReport` (`decision` is null until analysis is done) | — |
| 11 | `GET /api/sessions/{id}/frames/{idx}.jpg` | agent | — | `image/jpeg` | 404 |
| 12 | `POST /api/sessions/{id}/agent` | agent | `AgentDecision` | 204 | 409 before a decision exists |

Rules:
- **Customer responses never contain** `risk`, `flag`, `check_id`, `family`, `outcome` or any score. `CustomerStatus.message` is the only result the customer sees.
- Customer message mapping, done by the engine:

  | Outcome | Customer message |
  |---|---|
  | `PASS` | `continue` |
  | `RETRY_STEP_UP` with step-up `fresh_challenge` | `please_retry` |
  | `RETRY_STEP_UP` with `no_flash` or `agent_checks` | `please_wait` |
  | `RETRY_STEP_UP` with `assisted_kyc` | `assisted_route` |
  | `HUMAN_REVIEW` | `please_wait` |

  While the state is not `done`, the message is `please_wait`.
- The retry flow: `SessionCreate.previous_session_id` links a new attempt; `attempt` = previous + 1 (first = 1).

---

## 3. Python models: `server/pulselens/contracts.py` (pydantic v2)

Keshav creates this file at task K1 exactly as below. Ganeev and Yash read it; they never edit it.

```python
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


class SessionSummary(Model):
    session_id: str
    created_at_ms: int
    product: Product
    attempt: int
    state: SessionState
    mode: Mode | None
    outcome: Outcome | None
    label_kind: str | None


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
```

---

## 4. TypeScript mirror: `web/src/contracts.ts`

Keshav writes it by hand at K1, field for field, same names (snake_case). Mapping:
- `Literal[...]` becomes a string union.
- `X | None` becomes `X | null`.
- `tuple[...]` becomes a TS tuple.
- `dict[str, T]` becomes `Record<string, T>`.
- `Step` becomes `ColourStep | TurnStep`.

A pytest (`server/tests/engine/test_contract_mirror.py`) parses `contracts.ts` and fails if a model or field name in `contracts.py` is missing from it.

`web/src/api/client.ts` (Keshav) exports one typed function per row of the API table:

```ts
createSession(body: SessionCreate): Promise<SessionCreated>
postPreflight(id: string, token: string, body: Preflight): Promise<Plan>
getChallenge(id: string, token: string): Promise<Challenge>
postFrames(id: string, token: string, meta: FrameBatchMeta, jpegs: Blob[]): Promise<void>   // jpegs[i] belongs to meta.frames[i]
postEvents(id: string, token: string, events: ChallengeEvent[]): Promise<void>
completeSession(id: string, token: string): Promise<void>
getStatus(id: string, token: string): Promise<CustomerStatus>
listSessions(passcode: string): Promise<SessionSummary[]>
getResult(id: string, passcode: string): Promise<SessionReport>
frameUrl(id: string, idx: number): string
postAgentDecision(id: string, passcode: string, body: AgentDecision): Promise<void>
```

Every function throws `ApiError { status: number; detail: string }` on a non-2xx response.

---

## 5. Session bundle on disk

The engine writes it and the analysis reads it. Root: `data/sessions/<session_id>/` (`data/` is gitignored; `PULSE_DATA_DIR` overrides it).

| File | Written by | Content |
|---|---|---|
| `session.json` | engine, on create | `{session_id, nonce, product, no_flash, attempt, previous_session_id, created_at_ms, expires_at_ms, state, label}` |
| `preflight.json` | engine | `Preflight` |
| `plan.json` | engine | `Plan` |
| `challenge.json` | engine, when issued | `Challenge` |
| `frames.jsonl` | engine, per batch | one `FrameMeta` per line, plus `"batch_seq"` and `"received_at_ms"` |
| `frames/{idx:06d}.jpg` | engine | the JPEG exactly as uploaded |
| `events.jsonl` | engine | one `ChallengeEvent` per line |
| `integrity.json` | engine (K5) | `list[CheckResult]` with `check_id` `integrity.*` |
| `landmarks.jsonl` | analysis (cache) | per frame `{idx, landmarks: [[x, y, z] x 478] or null, yaw, pitch}`; synthetic bundles ship it so tests need no face model |
| `results.json` | engine, from the analysis' return value | `list[CheckResult]` (integrity + analysis) |
| `decision.json` | engine | `Decision` |
| `agent.json` | engine | `AgentDecision` |
| `audit.jsonl` | engine (K8) | hash-chained evidence events |

**Loader** (`server/pulselens/bundle.py`, Keshav, K1):

```python
@dataclass
class Bundle:
    path: Path
    session: dict
    preflight: Preflight | None
    plan: Plan | None
    challenge: Challenge | None
    frames: list[FrameMeta]          # sorted by idx
    events: list[ChallengeEvent]
    label: Label | None

    def frame_path(self, idx: int) -> Path: ...
    def read_frame(self, idx: int) -> "np.ndarray | None": ...   # BGR uint8 via cv2.imdecode; None if missing/corrupt; imports cv2 lazily

def load_bundle(path: Path) -> Bundle: ...                         # never raises on a missing optional file
def write_bundle(path: Path, *, session: dict, preflight: Preflight | None, plan: Plan | None,
                 challenge: Challenge | None, frames: list[tuple[FrameMeta, bytes]],
                 events: list[ChallengeEvent]) -> None: ...         # used by tests and synthetic fixtures
```

---

## 6. Analysis interface (Ganeev to Keshav)

```python
# server/pulselens/analysis/__init__.py  (Ganeev)
def analyze(session_dir: Path) -> list[CheckResult]:
    """Run every check of families A-D on a completed bundle. Never raises: a check that cannot
    judge returns status "abstain" with reason codes. Must finish in < 90 s for 900 frames on CPU."""
```

- The engine runs `integrity` (K5) first, then `analyze()`, then `fuse()` (K6), in a worker thread after `/complete`.
- Until Ganeev's G1 is merged, the engine uses `server/pulselens/engine/fake_analysis.py` (Keshav) when the env var `PULSE_FAKE_ANALYSIS=1` is set, or when `pulselens.analysis` has no `analyze`.
- If `analyze()` raises anyway, the engine records one result `analysis.error` (family B, status abstain) and goes on.

---

## 7. Reason codes

Format: `<area>.<what>`, lowercase, for example `quality.low_fps`, `light.no_echo`, `turn.wrong_direction`, `integrity.non_monotonic_time`, `mode.capable.ok`.

Each owner keeps a catalogue mapping code → one plain English sentence:
- **Engine (Keshav):** `server/pulselens/engine/reason_text.py`, with prefixes `integrity.`, `mode.`, `fusion.`, `analysis.`
- **Analysis (Ganeev):** `server/pulselens/analysis/reason_text.py`, with prefixes `quality.`, `sensor.`, `light.`, `turn.`, `visual.`, `pulse.`
- **Customer UI (Yash):** no reason codes. The customer never sees them.

A pytest owned by each side fails if a code that side emits is missing from its catalogue.

---

## 8. Fusion and outcome rules (implemented by Keshav, K6)

Input: all `CheckResult`s (integrity + analysis) and the `Plan`.

1. **Gate.** Only `status == "usable"` results count as evidence. `abstain` never counts for or against.
2. **Group.** Within a family, results with the same `vote_group` are one vote. The group flags if any member flags. Its risk is the max of the members' risks.
3. **Family state:**
   - `flag`: at least one group in the family flags.
   - `not_raised`: at least one usable result and no flags.
   - `abstained`: results exist, none usable.
   - `not_run`: no results for the family.
4. **Family A** (pulse) is reported but never votes, in rules 5 and 6 below.
5. **Outcome, first match wins:**

   | Order | Condition | Outcome | Step-up | Reason code |
   |---|---|---|---|---|
   | 1 | any result with `status == "protocol_error"` | `HUMAN_REVIEW` | — | `fusion.integrity_violation` |
   | 2 | 2 or more of B, C, D are `flag` | `HUMAN_REVIEW` | — | `fusion.two_families` |
   | 3 | exactly 1 of B, C, D is `flag` | `RETRY_STEP_UP` | `fresh_challenge`; `agent_checks` if mode is `NO_FLASH` or `attempt >= 2` | `fusion.one_family` |
   | 4 | fewer than 2 of B, C, D have a usable result | `RETRY_STEP_UP` | `no_flash` if C abstained with a `quality.*` light reason and mode is not `NO_FLASH`; else `agent_checks`; `assisted_kyc` if `attempt >= 3` | `fusion.low_coverage` |
   | 5 | otherwise | `PASS` | — | `fusion.pass` |

6. `Decision.provisional` is true if any usable result has `threshold_source == "provisional"`. The console then shows the label **PROVISIONAL THRESHOLDS**.

These rules are table-driven tests in K6. Changing them is a contract change.

---

## 9. Check catalogue (who emits what)

| check_id | Family | vote_group | Owner | Notes |
|---|---|---|---|---|
| `integrity.protocol` | B | `B.protocol` | Keshav | `protocol_error` on hard violations (K5) |
| `integrity.coverage` | B | `B.protocol` | Keshav | gaps, missing batches; usable or abstain, never protocol_error |
| `sensor.cadence` | B | `B.stream` | Ganeev | frame-interval statistics |
| `sensor.duplicates` | B | `B.stream` | Ganeev | near-duplicate frame runs |
| `sensor.mode_probe` | B | `B.probe` | Ganeev | from `Preflight.probe` |
| `sensor.regions` | B | `B.regions` | Ganeev | noise and sharpness, face vs neck vs background |
| `sensor.prnu` | B | `B.prnu` | Ganeev | supporting only: `flag` is always false |
| `light.response` | C | `C.response` | Ganeev | the face answers today's colour sequence |
| `light.face_neck` | C | `C.relative` | Ganeev | face echo relative to neck echo |
| `light.background` | C | `C.relative` | Ganeev | background responds less than the face |
| `turn.follow` | D | `D.turn` | Ganeev | yaw follows the requested direction and returns |
| `turn.identity` | D | `D.identity` | Ganeev | same face through the turn |
| `visual.sbi` | D | `D.detector` | Ganeev | SBI detector score, one feature |
| `pulse.coherence` | A | `A.pulse` | Ganeev | logged only; `flag` is always false |
