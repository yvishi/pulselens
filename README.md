# PulseLens

**Adaptive, camera-first liveness for video-KYC (RBI V-CIP).**

Team Mama Mia (Thapar Institute of Engineering and Technology): Ganeev Singh Tuteja, Yash Vishnoi, Keshav Juneja. Amazon AI Cyber Security Hackathon finale, Challenge 03.

## What PulseLens is

Video-KYC lets a bank open an account over a video call. That convenience is also an attack surface: a pre-recorded replay, a virtual camera, or a real person whose face is swapped live. PulseLens is a liveness layer for these calls that answers two questions on its own terms instead of producing one vague "deepfake score". First, is this a real camera, in this session? Second, does the face respond like a real face to a fresh light challenge and a head turn? Every call gets a new random screen-colour sequence and a random head-turn direction, tied to a single-use session nonce, so a recording made in advance cannot know what to answer. Each check judges its own capture quality and abstains when it cannot see well, so poor light or a budget phone leads to a retry, never a fraud flag. PulseLens recommends; a bank agent makes the final call.

## How it works

```
Applicant phone / browser          PulseLens service (FastAPI)                         Agent console
─────────────────────────          ───────────────────────────                         ─────────────
preflight + camera probe  ──►  planner: mode (CAPABLE / CONSTRAINED / NO_FLASH),
                               random colour order + timing, turn direction, nonce
colour challenge + head turn
frames + events (batched) ──►  integrity: session binding, timestamps, order, coverage
                               hash-chained audit log
                               analysis: quality gate per window, then four families
                                 A pulse (logged only) · B sensor & stream
                                 C light challenge     · D visual & motion
                               fusion: quality-aware, correlated cues collapsed  ──►  PASS · RETRY / STEP-UP ·
                                                                                       HUMAN REVIEW, with plain-
                                                                                       language reasons
                                                                                       approve · re-verify · escalate
```

1. **Capture** (`web/src/capture`, `web/src/customer`). The customer opens a link or QR code. The browser runs a quality preflight (fps, blur, brightness, motion) and probes which W3C Image Capture controls really work. It then paints the server's colour sequence on the screen, prompts the head turn with a yaw progress ring, and uploads JPEG frames and challenge events in batches. All times come from one clock (`performance.now()` relative to challenge start).
2. **Engine** (`server/pulselens/engine`, `server/pulselens/api`). The planner picks a capture mode from the measured device, never the device name, and the mode is never treated as a risk signal. After `/complete`, a worker thread checks integrity, runs the analysis with a timeout, fuses the results and writes `results.json` and `decision.json`. Every step is appended to a SHA-256 hash-chained `audit.jsonl`.
3. **Analysis** (`server/pulselens/analysis`). A quality gate scores each time window. Each check returns a risk, its quality, reason codes and a status (usable, abstain or protocol error), and abstained checks never count as attack evidence.
4. **Decision and review** (`web/src/console`). The agent sees the outcome, a plain-language reason for each family, the challenge timeline, feature plots and evidence frames, then approves, requests re-verification or escalates. Approve and escalate are final. Raw frames of customer sessions are deleted once the agent decides.

## Key features

**Capture (applicant device)**
- Quality preflight and a live camera-control probe. An unsupported control is reported as unsupported, never as a failure.
- Three adaptive capture modes: CAPABLE (full colour challenge and turn), CONSTRAINED (a slower, simpler colour challenge and turn) and NO_FLASH (turn plus agent-led checks, for photosensitivity or extreme light, which the customer can choose). The planner can downgrade mid-session if fps drops.
- A colour challenge with no red hues, and painted and ended timestamps for every colour step.
- A head-turn prompt that keeps recording after the turn so a slow head is seen coming back.
- Coaching tips in English and Hindi, weak-connection notices, camera error states, fullscreen, portrait lock and wake lock on phones.
- A `/lab` recording page for labelled volunteer sessions (pseudonymous codes, consent reference) that uses the same capture screens.

**Engine (service)**
- Single-use sessions with a nonce, a TTL and limits on frames and upload size. Each session gets a server-side plan and challenge.
- Integrity checks: monotonic timestamps, duplicate frame indices, event order, uploads after completion, and coverage (enough frames, few missing batches). A hard protocol violation and a weak physical cue get separate reason codes.
- Quality-aware fusion. Only usable, voting results count. Results in the same vote group are one vote. Family A is reported but never votes. Rules, first match wins:
  - **HUMAN REVIEW**: an integrity violation, or flags from two or more families.
  - **RETRY / STEP-UP**: one flagged family, a turn that was prompted but not performed, low coverage, or liveness not shown. The step-up is a fresh challenge, the no-flash path, agent checks, or assisted KYC (after repeated low-coverage attempts).
  - **PASS**: enough coverage, no flags, and the live challenge verified (the head turn followed, or the light answered when no turn ran).
- The customer only ever sees "continue", "please retry", "please wait" or the assisted route. They never see a score, family or outcome.
- Password-gated agent console with live polling, a question card for agent-led checks, family cards with uPlot charts, evidence frames, and re-verify links with QR codes.
- Privacy: raw frames are deleted on the agent's decision (`frames.deleted` in the audit chain), plus a purge CLI and an offline audit-chain verifier.

**Analysis (checks)**

| Family | Check | What it looks at |
|---|---|---|
| A · Pulse | `pulse.coherence` | face vs neck rPPG pulse agreement. Logged only, never votes |
| B · Sensor & stream | `sensor.cadence`, `sensor.duplicates` | frame-timing jitter and repeated frames (freezes, virtual-camera loops) |
| | `sensor.mode_probe` | whether the stream reacts to a real camera mode switch |
| | `sensor.regions` | noise residual across face, neck and background (measured, not voting yet) |
| | `sensor.prnu` | sensor fingerprint consistency (supporting only) |
| C · Light challenge | `light.response` | the face's colour echo of the random hue sequence: order, shape, lag |
| | `light.face_neck`, `light.background` | face response compared with the neck and the wall in the same session |
| D · Visual & motion | `turn.follow` | head yaw follows the requested direction. Flags a wrong-way turn or a frozen head, abstains if the turn was not performed |
| | `turn.identity` | face proportions before and after the turn |
| | `visual.sbi` | a pretrained Self-Blended Images detector (measured, not voting yet; needs weights downloaded by hand) |

Thresholds live in `server/pulselens/analysis/thresholds.yaml`. They are **provisional** until calibrated, and the console says so. `scripts/calibrate.py` sets each `flag_at` from labelled genuine sessions (set A only).

**Evaluation**: `eval/` computes APCER/BPCER, retry and abstain rates, latency and per-check separation (AUC). Config and thresholds are frozen by hash before the held-out set B is scored. With small samples these numbers show feasibility, not production accuracy.

## Repo layout

```
web/                      React 19 + Vite + TypeScript app
  src/capture/            camera, clock, preflight, probe, colour challenge, turn, encoder, uploader
  src/customer/           customer flow: consent, coaching, challenge, result (English and Hindi)
  src/console/            agent console: session list, session review, family cards, actions
  src/lab/                volunteer recording page
  e2e/                    Playwright tests (customer, lab, console, replay)
server/pulselens/
  api/                    FastAPI app: customer session routes and agent routes
  engine/                 planner, steps, store, integrity, runner, fusion, audit, auth, purge
  analysis/               quality gate, vision helpers (face, pose, pulse, noise, PRNU, SBI), checks/
  contracts.py, bundle.py shared types and the session bundle format
server/tests/             pytest: engine and analysis (golden decisions, synthetic fixtures)
eval/                     evaluation: load, run, separation, freeze, report
scripts/                  dev task runner, model fetchers, video ingest, calibration, purge, audit verify
docs/                     architecture, contract, plan, plan vs built, walkthrough, task and status files
config.yaml               planner, challenge, capture and session settings
```

## Getting started

Needs Python 3.11+ (or `uv`, which fetches it) and Node 22.12+. Everything runs through `scripts/dev.py` from the repo root on any OS (there is no make).

```bash
python scripts/dev.py setup      # .venv, Python deps, server package (editable), npm ci, .env, model downloads
python scripts/dev.py server     # FastAPI on http://127.0.0.1:8000 (uvicorn, reload)
python scripts/dev.py web        # Vite dev server on http://localhost:5173
python scripts/dev.py tunnel     # optional: cloudflared HTTPS tunnel, since phones need HTTPS for the camera
```

Set `AGENT_PASSCODE` in `.env` before a demo. `PULSE_FAKE_ANALYSIS=1` runs the engine with a clearly labelled fake analysis. The SBI weights (`models/sbi/FFc23.tar`) are downloaded by hand: see `scripts/fetch_models.py`.

Pages: `/` home, `/console` agent console, `/lab` volunteer recording, `/customer/:sessionId` customer capture.

Tests and lint:

```bash
python scripts/dev.py test       # pytest (server/tests)
python scripts/dev.py test-web   # tsc typecheck + vitest
python scripts/dev.py e2e        # Playwright in the installed Brave (BRAVE_PATH overrides); stop dev servers first
python scripts/dev.py lint       # ruff + ESLint
```

Useful tools:

```bash
python -m pulselens.analysis data/sessions/<id> [--plots]   # analyse one session (--all for every session in a folder)
python scripts/ingest_video.py <video>                      # turn a video file into a session and analyse it
python scripts/verify_audit.py data/sessions/<id>           # verify a session's hash-chained audit log
python scripts/calibrate.py --sessions data/sessions        # calibrate thresholds from genuine set A sessions
python scripts/purge.py                                     # delete demo sessions
```

## Docs

| Doc | What |
|---|---|
| [`AGENTS.md`](AGENTS.md) | rules for every coding agent (Claude Code, Codex, Cursor and others) |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | the reference architecture |
| [`docs/CONTRACT.md`](docs/CONTRACT.md) | shared types, API, bundle format, fusion rules |
| [`docs/WALKTHROUGH.md`](docs/WALKTHROUGH.md) | the pipeline end to end, with file pointers |
| [`docs/PLAN.md`](docs/PLAN.md) · [`docs/PLAN_VS_BUILT.md`](docs/PLAN_VS_BUILT.md) | the plan, and what was built against it |
| [`docs/tasks/`](docs/tasks) · [`docs/status/`](docs/status) | per-person task lists and status |
| [`docs/REFERENCE.md`](docs/REFERENCE.md) | old prototype, measured facts, sources |

## Team

| Who | Owned |
|---|---|
| **Yash Vishnoi** | capture: applicant device, customer and lab screens, UI, e2e tests |
| **Keshav Juneja** | engine: sessions API, planner, integrity, runner, fusion, audit, agent console, evaluation |
| **Ganeev Singh Tuteja** | analysis: quality gate, light, sensor, turn, identity, pulse and SBI checks, calibration |

## Privacy and ethics

- No heart rate or pulse waveform is ever stored.
- Raw frames of customer sessions are deleted once the agent decides. Results, decisions and the audit log stay.
- Volunteers are identified by pseudonymous codes only.
- No real public figures and no real bank data.
- This repo contains only the detector. Attack tooling is used offline to red-team our own system, and no attack code is published.
