# Keshav: engine, console and evaluation (K1 to K11)

**You own:** the repo scaffold, the shared contract code, the FastAPI server, the session orchestrator and challenge planner (service step 1), ingest and frame integrity (step 2), evidence fusion and policy outcomes (steps 4 and 5), the agent review console, the evidence record, and evaluation.

**Your paths:** see `docs/PLAN.md` section 2. Never edit `server/pulselens/analysis/**` (Ganeev) or `web/src/capture|customer|lab/**` (Yash).

**Before each task:** read `docs/CONTRACT.md` sections named in the task.

**After each task:**
- Run `python scripts/dev.py test`, `test-web` and `lint`.
- Tick the task in `docs/status/keshav.md`.
- Open a PR and merge it (never delete the branch).

**Port from the old repo** (`../PulseLensFinal-ref`, see `docs/REFERENCE.md`). Read, simplify and re-test; do not copy whole files blindly.

---

## K1. Scaffold and contract (H0–1, blocking everyone)

**Do this first and fast:** the other two pull `main` at H1.

**Files to create:**
- **Repo root:** `.env.example`, `config.yaml`, `scripts/dev.py`. (`.gitignore` already exists in the planning commit; extend it if needed, never remove `data/`, `models/` or `.env`.)
- **Server:**
  - `server/pyproject.toml`: package `pulselens` in `server/`; pytest `testpaths = ["server/tests"]`; ruff line-length 120, target py311, rules E, F, W, I, UP, B.
  - `server/requirements/engine.txt`: `fastapi`, `uvicorn[standard]`, `pydantic>=2.7`, `python-multipart`, `numpy`, `pyyaml`, `httpx`, `pytest`, `ruff`.
  - `server/requirements/analysis.txt`: an **empty placeholder** with the comment `# owned by Ganeev`.
  - `server/pulselens/__init__.py`, `contracts.py` (exactly `docs/CONTRACT.md` §3), `bundle.py` (§5), `config.py`.
  - `server/pulselens/analysis/__init__.py`: placeholder with the one line `"""Owned by Ganeev. analyze() arrives in G1."""`.
  - `server/pulselens/api/main.py` (FastAPI app with `GET /api/health`).
  - `server/tests/conftest.py`, `server/tests/engine/test_contract_mirror.py`, `server/tests/engine/test_bundle.py`.
- **Web:**
  - `web/package.json` with these dependencies:
    - runtime: `react@19`, `react-dom@19`, `react-router-dom@7`, `uplot`, `qrcode`, `@mediapipe/tasks-vision`
    - dev: `vite@7`, `@vitejs/plugin-react`, `typescript@5.9`, `vitest`, `jsdom`, `@testing-library/react`, `@playwright/test`, `eslint`, `typescript-eslint`, `@types/react`, `@types/react-dom`, `@types/qrcode`
  - `web/vite.config.ts`: port 5173; proxy `/api` → `http://127.0.0.1:8000`; `server.allowedHosts: [".trycloudflare.com"]`; vitest env `jsdom`.
  - `web/tsconfig.json`: strict.
  - `web/eslint.config.js`: add the rule `no-restricted-properties` banning `Date.now` in `src/**` (one clock, CONTRACT §1).
  - `web/playwright.config.ts`: Chromium with `--use-fake-device-for-media-stream` and `--use-fake-ui-for-media-stream`; `webServer` starts the server with `PULSE_FAKE_ANALYSIS=1 PULSE_DATA_DIR=data/e2e`, plus Vite.
  - `web/index.html`, `web/src/main.tsx`, `web/src/App.tsx`, `web/src/contracts.ts` (§4), `web/src/api/client.ts` (§4).
  - `web/src/shared/styles.css` (mobile-first base, body ≥ 16 px), `web/src/shared/HonestyLabel.tsx`.
  - Placeholders `web/src/customer/CustomerPage.tsx` and `web/src/lab/LabPage.tsx` (Yash's from then on), and `web/src/console/ConsoleList.tsx`, `web/src/console/ConsoleSession.tsx`.
  - `web/src/App.test.tsx`.
- **Docs:** `docs/status/{yash,keshav,ganeev}.md` already exist; leave them.

**`App.tsx` routes (final; nobody edits them later):**
- `/` → a home page with links "Customer demo (from the console)", "Lab recording" and "Agent console"
- `/customer/:sessionId` → `CustomerPage` (lazy)
- `/lab` → `LabPage` (lazy)
- `/console` → `ConsoleList`
- `/console/:sessionId` → `ConsoleSession`

**`.env.example`:** `AGENT_PASSCODE=change-me`, `PULSE_DATA_DIR=data/sessions`, `PULSE_FAKE_ANALYSIS=0`. The server logs a warning while the passcode is `change-me`.

**`config.yaml`** (read by `config.py`; Yash mirrors the `capture` block in his own constants file):
```yaml
planner:
  capable_min_fps: 20          # PROVISIONAL: old repo profile band edge
  light_min_fps: 12            # below this the light challenge is not run (old repo quality.min_fps)
  brightness_range: [40, 220]  # mean luma; above 220 = too bright for the screen light to matter
  min_face_fraction: 0.02
challenge:
  baseline_ms: 1500
  hues_deg: [40, 80, 140, 200, 250, 300]   # no red: nothing in [345, 15]
  turn_gap_ms: 1000
  capable:     {colour_steps: 6, dwell_ms: 400, gap_ms: [700, 1300], turn_ms: 3000}
  constrained: {colour_steps: 4, dwell_ms: 700, gap_ms: [1000, 1600], turn_ms: 3500}
  no_flash:    {turn_ms: 3500}
capture:
  desktop_size: [640, 480]
  mobile_size: [480, 360]
  jpeg_quality: 0.9
  upload_batch_ms: 1000
session:
  ttl_min: 15
  max_frames: 900
  max_batch_frames: 30
  max_jpeg_kb: 200
analysis:
  timeout_s: 120
```

**`scripts/dev.py` targets:** `setup`, `server`, `web`, `tunnel`, `test`, `test-web`, `e2e`, `lint`.
- `setup` does these in order:
  1. `uv venv .venv --python 3.11` (falls back to `python -m venv` if `uv` is missing)
  2. install both requirements files
  3. `npm ci` in `web/`, then `npx playwright install chromium`
  4. copy `.env.example` to `.env` if it is missing
  5. run `scripts/fetch_models.py` and `scripts/fetch_web_models.py` **if they exist**
- Use `subprocess` with lists, and the venv Python path for the platform.
- Port the runner style from the old `scripts/dev.py`.

**Tests:**
- `test_contract_mirror.py::test_every_model_and_field_is_in_ts`: parses `web/src/contracts.ts` (regexes for `export interface X` / `export type X` and `field:`) and asserts every pydantic model and field name in `contracts.py` appears.
- `test_bundle.py::test_roundtrip`:
  - `write_bundle` writes 3 frames and 2 events.
  - `load_bundle` gives `frames` sorted by idx, the same events, and `read_frame(1)` with shape (h, w, 3).
- `test_bundle.py::test_missing_optional_files`: a dir with only `session.json` loads with `preflight is None` and `frames == []`.
- `App.test.tsx`: `/` renders 3 links.
- `GET /api/health` returns 200 `{"ok": true}` (httpx `TestClient`).

**Done when:** `python scripts/dev.py setup` works on a fresh clone on Windows, and test, test-web and lint pass. Merge, then tell Yash and Ganeev.

---

## K2. Sessions API, ingest and storage (H1–4)

**Read:** CONTRACT §2, §5.

**Files:**
- `server/pulselens/api/sessions.py` (`APIRouter`)
- `server/pulselens/engine/store.py`
- `server/pulselens/engine/auth.py`
- `server/tests/engine/test_api_sessions.py`

**Interfaces you produce:**
```python
# engine/store.py
class SessionStore:
    def __init__(self, root: Path): ...
    def create(self, body: SessionCreate) -> SessionCreated: ...      # writes session.json, audit "session.created"
    def get(self, session_id: str) -> dict: ...                       # raises KeyError
    def set_state(self, session_id: str, state: SessionState) -> None: ...
    def path(self, session_id: str) -> Path: ...
    def save_model(self, session_id: str, name: str, model: BaseModel) -> None: ...   # e.g. "plan.json"
    def append_frames(self, session_id: str, meta: FrameBatchMeta, jpegs: list[bytes]) -> None: ...
    def append_events(self, session_id: str, events: list[ChallengeEvent]) -> None: ...
    def list(self) -> list[SessionSummary]: ...
# One threading.Lock per session id for every write.
```

**Build:**
- Every route of the CONTRACT §2 table except `/result`, `/agent` and `/frames/{idx}.jpg` (those are in K7).
- `/preflight` calls `plan_session` (K3), saves `preflight.json` and `plan.json`, and sets the state to `preflight`.
- `/challenge`:
  - calls `make_challenge` (K3) once and saves `challenge.json`;
  - sets the state to `capturing`;
  - a second call returns 409 `challenge_already_issued`.
- `/complete` sets the state to `analysing` and starts `run_analysis` (K4) on a `ThreadPoolExecutor(max_workers=2)`.
- Tokens:
  - `customer_token = hmac.new(secret, session_id.encode(), sha256).hexdigest()[:32]`;
  - the secret is `secrets.token_bytes(32)`, generated at startup and kept in memory (a server restart invalidates open sessions; fine for the demo);
  - compare with `hmac.compare_digest`.
- **Limits (413):** more than 30 frames in a batch, a JPEG over 200 KB, or more than 900 frames in total.
- **Expiry:** after `ttl_min` every customer call returns 410, and the state becomes `expired`.

**Tests** (`TestClient`, `tmp_path` as `PULSE_DATA_DIR`, `PULSE_FAKE_ANALYSIS=1`):
- `test_create_returns_tokens_and_url`: 201; `customer_url == f"/customer/{id}?t={token}"`; `attempt == 1`.
- `test_previous_session_sets_attempt`: second create with `previous_session_id` → `attempt == 2`.
- `test_customer_auth_required`: preflight without a token → 401; with a wrong one → 401.
- `test_challenge_is_single_use`: second GET → 409 with `detail == "challenge_already_issued"`.
- `test_challenge_before_preflight`: 409 `no_plan`.
- `test_frames_written`: one batch of 3 JPEGs → `frames/000000.jpg` to `000002.jpg` and 3 lines in `frames.jsonl`.
- `test_limits`: 31 frames → 413; a 201 KB JPEG → 413.
- `test_frames_after_complete`: 409.
- `test_customer_payloads_have_no_scores`:
  - Run a full session with fake analysis, then GET `/status`.
  - Its JSON keys are exactly `{"state", "message"}`.
  - The serialized text of every customer response in the test contains none of `risk`, `flag`, `check_id`, `family`, `outcome`.
- `test_expired_session`: monkeypatch the clock past the TTL → 410.

---

## K3. Planner and challenge (H1–3, pure functions)

**Read:** CONTRACT §3 (`Preflight`, `Plan`, `Challenge`), `docs/ARCHITECTURE.md` "Adaptive capture".

**Files:**
- `server/pulselens/engine/planner.py`
- `server/pulselens/engine/reason_text.py` (start the catalogue)
- `server/tests/engine/test_planner.py`

**Interfaces:**
```python
def plan_session(pre: Preflight, session_no_flash: bool, cfg: dict) -> Plan: ...
def make_challenge(plan: Plan, session_id: str, nonce: str, rng: random.Random, cfg: dict) -> Challenge: ...
# The API seeds rng with int.from_bytes(sha256(nonce).digest()[:8]): reproducible per session, unpredictable across sessions.
```

**Planner rules (first match wins; reasons use these codes):**

| # | Condition | Plan | Reason code |
|---|---|---|---|
| 1 | `session_no_flash` or `pre.no_flash_requested` | NO_FLASH, light off, turn on, agent questions on | `mode.no_flash.requested` |
| 2 | `pre.brightness > 220` | NO_FLASH, light off, turn on, agent questions on | `mode.no_flash.too_bright` |
| 3 | `pre.measured_fps < light_min_fps (12)` | CONSTRAINED, light off, turn on, agent questions on | `mode.constrained.fps_too_low_for_light` |
| 4 | `fps >= 20` and brightness in [40, 220] and `face_fraction >= 0.02` | CAPABLE, light on, turn on, agent questions off | `mode.capable.ok` |
| 5 | otherwise | CONSTRAINED, light on, turn on, agent questions off | one code per failed sub-condition: `mode.constrained.fps`, `mode.constrained.dim`, `mode.constrained.small_face` |

Also:
- If `pre.face_found` is false, add the reason `mode.face_not_found` and set agent questions on.
- **The mode is never a risk label.** Nothing downstream may treat CONSTRAINED or NO_FLASH as suspicious.

**Challenge:**
- `baseline_ms` comes from config.
- **Colour steps** (when light is on):
  - n = `colour_steps` for the mode;
  - hues = a random sample without replacement from `hues_deg` (6 of 6 for CAPABLE, 4 of 6 for CONSTRAINED), in random order;
  - each step's `start_offset_ms` = the previous step's end + uniform integer in `gap_ms` (the first starts at 0);
  - `dwell_ms` comes from the mode.
- **Turn step** (when on):
  - `direction` = `rng.choice(["left", "right"])`;
  - it starts `turn_gap_ms` after the last colour step ends (at 0 if there are no colour steps);
  - `duration_ms` = `turn_ms`.
- `total_ms` = the end of the last step + 500.
- Step ids are `c0..c5` and `t0`.

**Tests:**
- One test per planner row:
  - `test_rule1_no_flash`, `test_rule2_too_bright`, `test_rule3_low_fps`
  - `test_rule4_capable` (fps 30, brightness 120, face 0.1)
  - `test_rule5_constrained_dim` (fps 25, brightness 30, so the reasons include `mode.constrained.dim`)
- `test_every_reason_has_text`: every code the planner can emit is in `reason_text.py`.
- `test_challenge_safety`, over 200 seeds:
  - no hue in [345, 360) ∪ [0, 15];
  - steps don't overlap;
  - colour changes per second ≤ 3 (on and off both count) in every 1 s window;
  - CAPABLE has 6 colour steps + 1 turn; NO_FLASH has 0 colour steps + 1 turn.
- `test_challenge_random_per_nonce`: two nonces give different hue orders in ≥ 95 of 100 pairs; the same nonce gives an identical challenge.

---

## K4. Analysis runner and fake analysis (H3–5)

**Files:**
- `server/pulselens/engine/runner.py`
- `server/pulselens/engine/fake_analysis.py`
- `server/tests/engine/test_runner.py`

**Interfaces:**
```python
def run_analysis(session_dir: Path, store: SessionStore) -> Decision: ...
# 1. bundle = load_bundle(session_dir)
# 2. integrity = check_integrity(bundle)            (K5)
# 3. results = analyze(session_dir)                 (Ganeev's; or fake_analysis.analyze when PULSE_FAKE_ANALYSIS=1
#    or when pulselens.analysis has no `analyze`). Wrapped in try/except and a timeout of analysis.timeout_s:
#    on error or timeout, add one CheckResult(check_id="analysis.error", family="B", vote_group="B.analysis",
#    status="abstain", risk=None, flag=False, quality=0, explanation="Analysis did not finish.",
#    threshold_source="rule", reason_codes=["analysis.error"])
# 4. decision = fuse(integrity + results, bundle.plan, attempt)   (K6)
# 5. write results.json and decision.json; state = "done"; audit "analysis.done" and "decision.made" (K8)
```
- `fake_analysis.analyze(session_dir)` returns one usable, unflagged result for each of B, C and D (`check_id`s `fake.b`, `fake.c`, `fake.d`), with `threshold_source="provisional"` and explanation "FAKE ANALYSIS: not a real measurement." The console must show the explanation text.

**Tests:**
- `test_runner_with_fake`: a full bundle → `decision.json` exists, state `done`, outcome `PASS`.
- `test_runner_survives_analysis_exception`: monkeypatch `analyze` to raise → an `analysis.error` result exists and the state is `done`.
- `test_runner_timeout`: an `analyze` that sleeps past a 1 s test timeout → `analysis.error`.

---

## K5. Ingest integrity: service step 2 (H4–6)

**Read:** CONTRACT §5, §9 (`integrity.*`), `docs/ARCHITECTURE.md` step 2.

**Files:**
- `server/pulselens/engine/integrity.py`
- `server/tests/engine/test_integrity.py`

**Interface:** `def check_integrity(bundle: Bundle) -> list[CheckResult]`. It returns exactly two results, `integrity.protocol` and `integrity.coverage`, both family B with `vote_group` `B.protocol`.

**`integrity.protocol`:** `status = "protocol_error"` if any rule below is broken; otherwise `usable` with risk 0. `threshold_source = "rule"`. Each broken rule adds its reason code:

| Rule | Reason code |
|---|---|
| frame `t_ms` strictly increasing by `idx` | `integrity.non_monotonic_time` |
| no duplicate `idx` | `integrity.duplicate_index` |
| every event `step_id` exists in `challenge.json` | `integrity.unknown_step` |
| shown events in the challenge's step order by `painted_t_ms` | `integrity.event_order` |
| no frame or event received after `/complete` (enforced by the API; recorded if attempted) | `integrity.after_complete` |
| frames exist but `challenge.json` doesn't | `integrity.no_challenge` |

**`integrity.coverage`:** never `protocol_error`.
- Features: `frames`, `batch_gaps`, `span_ms`, `frames_per_step_window`.
- `abstain` with `integrity.too_few_frames` if fewer than 50 frames.
- Otherwise `usable`, with `risk = min(1, missing_batches / total_batches)` and `flag = risk >= 0.2`.
- Its explanation states the numbers.

**Tests:**
- One per rule, built with `write_bundle`.
- `test_clean_bundle_is_usable`.
- `test_network_gap_is_not_protocol_error`: batch_seq 0, 1, 3 → coverage reports the gap, and protocol is `usable`.

---

## K6. Fusion and outcomes: steps 4 and 5 (H4–7)

**Read:** CONTRACT §8 completely.

**Files:**
- `server/pulselens/engine/fusion.py`
- extend `reason_text.py`
- `server/tests/engine/test_fusion.py`

**Interfaces:**
```python
def fuse(results: list[CheckResult], plan: Plan | None, attempt: int) -> Decision: ...
def customer_message(state: SessionState, decision: Decision | None) -> CustomerMessage: ...
```

**Build:**
- Exactly CONTRACT §8.
- `Decision.reasons`: the outcome sentence first, then one sentence per flagged family, then one per abstained family. Use the result `explanation`s and the reason texts; never invent numbers.
- `FamilySummary.reasons`: the `explanation` of each flagged result, then each abstained one.

**Tests** (table-driven, one row per case, with results built by a helper `r(family, status, flag, group="X")`):
- `test_protocol_error_wins` (even when everything else passes) → HUMAN_REVIEW.
- `test_two_families` (B and C flag) → HUMAN_REVIEW.
- `test_same_family_two_checks_is_one_family` (two B groups flag, C and D clean) → RETRY_STEP_UP / `fresh_challenge`.
- `test_correlated_cues_one_vote`: `sensor.cadence` and `sensor.duplicates` both flag in `B.stream` → B counts once.
- `test_family_a_never_votes`: A flags, B and C flag → still HUMAN_REVIEW only through B + C; and A + B flagging alone → RETRY.
- `test_one_family_no_flash` → `agent_checks`.
- `test_one_family_attempt2` → `agent_checks`.
- `test_low_coverage_light_quality` → `no_flash`.
- `test_low_coverage_attempt3` → `assisted_kyc`.
- `test_abstain_never_counts`: every check abstains except B and D usable and unflagged → PASS.
- `test_pass`.
- `test_provisional_flag`.
- `test_customer_message_mapping`: every row of the CONTRACT §2 table.

---

## K7. Agent console (v1 by S1 at H8, v2 by H16)

**Read:** CONTRACT §2 rows 9–12, `docs/ARCHITECTURE.md` "Agent review console", and the deck's slide 9 mock-up (described in `docs/REFERENCE.md`).

**Files:**
- **Server:** add `/result`, `/agent`, `/frames/{idx}.jpg` and `GET /api/sessions` to `api/sessions.py`.
- **Web:** `web/src/console/**` (`ConsoleList.tsx`, `ConsoleSession.tsx`, `FamilyCard.tsx`, `Timeline.tsx`, `CheckPlot.tsx`, `OutcomeBanner.tsx`, `AgentActions.tsx`, `NewSession.tsx`, `passcode.ts`).
- **e2e:** `web/e2e/console.spec.ts`.

**v1 (by S1):**
- `/console` asks for the passcode once (kept in `sessionStorage`) and lists sessions (polling every 2 s).
- `/console/:id` polls `getResult` every 1 s until a decision exists, then shows:
  - the outcome banner;
  - four family cards with their state;
  - the result explanations.

**v2 (by H16):** the deck's console.
- **Header:** session id, product, attempt, mode with plan reasons, **PROVISIONAL THRESHOLDS** label when `decision.provisional`, and a FAKE ANALYSIS label when any `check_id` starts with `fake.`.
- **Challenge timeline:** a horizontal strip with the requested steps from `challenge.json` (colour swatches at their offsets, the turn arrow) and the observed events under it (painted times, skipped steps marked).
- **Evidence by family**, cards A, B, C, D:
  - state chip `FLAG` / `NOT RAISED` / `ABSTAINED` / `NOT RUN`;
  - **failed and abstained listed separately**;
  - each check expands to show its explanation, its features as a table, and its `plot` drawn with uPlot (series and markers);
  - family A has the label "experimental, not used in the decision".
- **Evidence frames:** thumbnails of 6 frames (one per colour step's `painted` time and the turn's peak) via `frameUrl`.
- **Outcome banner:**
  - PASS green, RETRY / STEP-UP amber, HUMAN REVIEW red;
  - the reasons;
  - the step-up suggestion;
  - the line "PulseLens recommends; the agent decides."
- **Agent actions:**
  - buttons Approve / Re-verify / Escalate to fraud, plus a note;
  - after an action, show the action and its time;
  - Re-verify calls `createSession({previous_session_id})` and shows the new customer link.
- **Layout:** readable at 1920×1080 and 1366×768; body text ≥ 18 px on the console.

**Tests (`console.spec.ts`, with `PULSE_FAKE_ANALYSIS=1`):**
- `test_passcode_required`: no passcode → no data.
- `test_session_reaches_decision`:
  - create a session through the API and post a minimal bundle (preflight, challenge, 60 synthetic JPEGs, events, complete);
  - the console shows a PASS banner and the FAKE ANALYSIS label within 10 s.
- `test_no_overflow`: at both resolutions no element has `scrollWidth > clientWidth`.
- `test_agent_action_recorded`: Approve → `agent.json` exists and the action shows on reload.

---

## K8. Evidence record (H12–16)

**Files:**
- `server/pulselens/engine/audit.py`
- `scripts/verify_audit.py`
- `server/tests/engine/test_audit.py`

**Interfaces:**
```python
def append(session_dir: Path, event_type: str, payload: bytes | dict) -> str: ...   # returns the new hash
def verify(session_dir: Path) -> tuple[bool, int | None]: ...                    # (ok, first bad line number)
```
- One line per event: `{seq, at_ms, type, payload_sha256, prev_hash, hash}`.
- `hash = sha256((prev_hash + canonical_json(line without "hash")).encode())`; `prev_hash` of the first line is 64 zeros.
- `canonical_json` = `json.dumps(sort_keys=True, separators=(",", ":"))`.
- Event types:

  | Type | Payload hashed |
  |---|---|
  | `session.created` | the session JSON |
  | `challenge.issued` | the challenge JSON |
  | `frames.batch` | the bytes of all JPEGs in the batch, concatenated, plus the meta JSON |
  | `events.received` | the events JSON |
  | `analysis.done` | the `results.json` bytes |
  | `decision.made` | the decision JSON |
  | `agent.action` | the agent action JSON |

- Wire the calls into K2, K4 and K7.

**Tests:**
- `test_chain_verifies`.
- `test_one_byte_change_detected`: flip one byte in a stored frame, re-hash that batch's payload → `verify` reports the line.
- `test_reordered_lines_detected`.

---

## K9. Pairing for phones and the tunnel (H8–12)

**Files:**
- `web/src/console/NewSession.tsx`
- the `tunnel` target in `scripts/dev.py`

**Build:**
- **NewSession:** a "New session" button on `/console` with a product select and a no-flash checkbox.
  - It calls `createSession`.
  - It shows the full customer URL (`window.location.origin` + `customer_url`) as text, as a QR code (the `qrcode` package, canvas ≥ 240 px), and as a copy button.
- **`tunnel`:** runs `cloudflared tunnel --url http://localhost:5173` and prints the https URL.
  - Document in `docs/status/keshav.md` that the console must be opened **through the tunnel URL**, so that the QR codes point to HTTPS.

**Test:** `console.spec.ts::test_new_session_shows_qr` checks that the canvas exists and the link contains `/customer/`.

---

## K10. Evaluation (part a by S2 at H18, part b by S3 at H30)

**Read:** `docs/PLAN.md` section 4, `docs/ARCHITECTURE.md` "India readiness and evaluation".

**Files:**
- `eval/__init__.py`, `eval/load.py`, `eval/separation.py`, `eval/run.py`, `eval/report.py`, `eval/freeze.py`
- `server/tests/engine/test_eval.py`

**K10a, by S2: `eval/separation.py`.**
- For every labelled session in set A that has `results.json`, and for each `check_id`: the AUC of `risk` for genuine vs each attack `kind`. Usable results only.
- Print "AUC 0.83 (genuine n=24, live_swap n=8)".
- Write `eval/out/separation.csv`.

**K10b, by S3:**
- **`run.py`:**
  - re-runs `fuse` on stored results, with an optional `--voting-off check_id,...` (the S3 "measured, not voting" list);
  - prints per attack kind: APCER = attacks with outcome PASS, as "x of n" with a Wilson 95% interval;
  - BPCER = genuine sessions with outcome HUMAN_REVIEW;
  - retry rate = genuine sessions with RETRY_STEP_UP;
  - abstain rate per family;
  - median and p95 time from `/complete` to the decision;
  - all broken down by `device`, `light` and capture mode;
  - **set B only** for the headline table; set A shown separately and labelled "tuning set".
- **`freeze.py`:** writes `eval/FROZEN` with the sha256 of `config.yaml`, `server/pulselens/analysis/thresholds.yaml`, `server/pulselens/analysis/thresholds.calibrated.yaml` and the voting-off list. `run.py --set B` refuses (exit 2) if FROZEN is missing or a hash differs.
- **`report.py`:** writes `eval/out/report.md` with the tables, every number as "x of n" with its interval, and the sentence "Small samples: feasibility evidence, not production accuracy."

**Tests:**
- `test_wilson_interval` against known values (x=0, n=10 → upper ≈ 0.278).
- `test_set_b_refused_without_freeze`.
- `test_freeze_detects_change`.
- `test_apcer_bpcer_on_synthetic` (fake results.json files).

---

## K11. Hardening (H24–36)

**Build:**
- **Timeouts:** API calls return within 2 s; analysis has its timeout.
- **`scripts/purge.py`:** deletes all `data/sessions/*` whose `label` is null and that are older than 60 minutes (demo sessions). It runs at server start and every 10 minutes in a background task. `--all-volunteers` deletes labelled sessions after the event (it asks for the typed confirmation `DELETE`).
- **`/console` "Reset demo" button:** hides sessions older than 1 h from the list; it does not delete.
- **Error messages:** a clear message on the console when the server is unreachable.

**Tests:**
- `test_purge_keeps_labelled`.
- `test_purge_removes_old_demo`.

---

## Sync duties
- **S1:** you run the manual walking-skeleton session with Yash.
- **S2:** run `eval/separation.py` and paste the output in `docs/status/keshav.md`.
- **S3:** run `freeze.py`, `run.py --set B` and `report.py`; give the numbers to the deck owner.
