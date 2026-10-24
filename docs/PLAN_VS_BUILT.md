# PulseLens: plan vs. built

Criterion 5: what we promised in `docs/PLAN.md`, what is merged on `main`, and what is still open. Every PR number links to
yvishi/pulselens; every "done" line is backed by a status file (`docs/status/*.md`). Snapshot: 2026-10-24.

## 1. Summary

| | Count | Notes |
|---|---|---|
| Planned tasks | 33 | Y0–Y10, K1–K11, G1–G11 (`docs/tasks/*.md`) |
| Code merged | 32 | every task except Y0 (device prep, a human task) |
| Waiting on a human step | 3 | Y0 phone + tunnel, Y7 real-device test, G9 calibration run (needs ≥ 20 genuine sessions) |
| Cut | 0 | all 8 cut-list items were built (section 3) |
| Beyond the plan | 4 | judge video ingest, frame deletion on decision, walkthrough, this report |

Tests on `main` at this snapshot: pytest 460 passed, 3 skipped (no model weights); vitest 209 passed; ruff and ESLint clean.

Thresholds are **provisional** (physics guesses, not measurements); the console says so on every session (section 5).

## 2. Per task

### Yash: applicant device and customer screens

| Task | Status | What is merged | PR |
|---|---|---|---|
| Y0 | **Not done** (human) | `cloudflared` and an Android phone on mobile data; `scripts/dev.py tunnel` exists | — |
| Y1 | Done | camera, one clock (`performance.now`), frame grabber, JPEG encoder | #19 |
| Y2 | Done | quality preflight and the mode-switch probe | #21 |
| Y3 | Done | colour challenge renderer, painted/ended timestamps | #20 |
| Y4 | Done | batch uploader (retries keep the same `batch_seq`), customer flow v1 | #24 |
| Y5 | Done | head-turn prompt with the yaw progress ring (guidance only) | #26 |
| Y6 | Done | coaching tips, no-flash path, English and Hindi | #27 |
| Y7 | Code done; **device test pending** | fullscreen, portrait lock, wake lock, `100dvh` | #30, #32 |
| Y8 | Done | `/lab` recording form (pseudonymous P/D codes, consent ref) | #25 |
| Y9 | Done | fps-drop downgrade, weak-connection notice, camera error states, `?lock=1` exposure lock | #31 |
| Y10 | Done | Brave e2e: customer, lab, replay attack | #29 |

Integration PRs: #28, #32.

### Keshav: engine, console, evidence record, evaluation

| Task | Status | What is merged | PR |
|---|---|---|---|
| K1 | Done | contract (`contracts.py` / `contracts.ts`), `bundle.py`, `scripts/dev.py` | #1 |
| K2 | Done | sessions API, `SessionStore`, HMAC customer token, size limits | #3 |
| K3 | Done | planner (CAPABLE / CONSTRAINED / NO_FLASH) and per-nonce challenge | #2 |
| K4 | Done | analysis runner (errors and timeouts become `analysis.error`) and fake analysis | #15 |
| K5 | Done | `integrity.protocol` and `integrity.coverage` | #14 |
| K6 | Done | fusion: usable-only gate, one vote per vote group, PASS / RETRY_STEP_UP / HUMAN_REVIEW | #13 |
| K7 | Done | agent console: session list, review, timeline, family cards, actions | #18, #23 |
| K8 | Done | hash-chained `audit.jsonl` and `scripts/verify_audit.py` | #39 |
| K9 | Done | new-session panel with link, QR and copy | #34 |
| K10 | Done | eval: AUC per check, APCER/BPCER with Wilson 95% CIs, freeze, report | #16, #37 |
| K11 | Done | purge of unlabelled sessions after 60 min, console "Reset demo" | #36 |

### Ganeev: analysis

| Task | Status | What is merged | PR |
|---|---|---|---|
| G1 | Done | analysis skeleton, vision base (MediaPipe landmarks, face/neck/background regions), synthetic bundles | #4 |
| G2 | Done | per-window quality gate | #8 |
| G3 | Done | `light.response` with the echo helper; weak-echo fix | #7, #35 |
| G4 | Done | `sensor.cadence`, `sensor.duplicates`; lost-frames fix | #6, #38 |
| G5 | Done | `light.face_neck`, `light.background` | #9 |
| G6 | Done | `turn.follow` | #11 |
| G7 | Code done | `visual.sbi`; **weights not installed**, so it abstains (`visual.model_missing`). Research-only licence | #41 |
| G8 | Done | `sensor.mode_probe`, `sensor.regions`, `sensor.prnu` (not voting) | #40 |
| G9 | Code done; **not run** | `scripts/calibrate.py` (genuine set A 97.5th percentile, ≥ 20 per check, never set B) | #95 |
| G10 | Done | `turn.identity` (votes) and `pulse.coherence` (logged only, never votes) | #90, #94 |
| G11 | Done | speed (≈ 12 s warm per 900 frames) and nuisance robustness (flicker, glare, JPEG 50) | #81 |

### Beyond the plan

| What | PR |
|---|---|
| `scripts/ingest_video.py`: a judge's video file → session bundle → analysis → console | #88 |
| Raw frames of `/customer` sessions deleted when the agent decides (`delete_frames_on_decision`), `frames.deleted` audit event | #89 |
| `docs/WALKTHROUGH.md` | #91 |
| This report | #93 |

Also merged: review fixes #42–#57 and #75–#87 (refactors guarded by golden decisions), UI redesign #92.

## 3. Cut list (PLAN §7)

None of the eight items was cut.

| Item | Outcome |
|---|---|
| 1. `pulse.coherence` | Built (#94), logged only: `voting: false`, never stores a heart rate or waveform |
| 2. `turn.identity` | Built (#90), votes in `D.identity` |
| 3. `sensor.prnu` | Built (#40), not voting (`flag` always false) |
| 4. `light.background` | Built (#9) |
| 5. Hindi strings | Built (#27); native-speaker check still pending |
| 6. Exposure lock | Built (#31), `?lock=1` |
| 7. Evidence-record hash chain | Built (#39) |
| 8. Lab recording screen | Built (#25) |

## 4. Privacy as built

- `/customer` session frames are deleted when the agent decides; `/lab` sessions (labelled, consented) are kept for calibration.
- Unlabelled sessions are purged after 60 minutes.
- The hash-chained audit record stays; `verify_audit.py` accepts the `frames.deleted` event.
- No heart rate or pulse waveform is written anywhere; the customer never sees a score, check or outcome (e2e `FORBIDDEN_WORDS`).

## 5. Known gaps (honest)

- **No calibration yet.** `calibrate.py` needs ≥ 20 genuine set A results per check; we have 3 genuine sessions. Every
  threshold is provisional.
- **Small real-data set.** 3 genuine and 8 live-swap (Deep-Live-Cam) recordings, one person and one device; 0 `replay_screen`
  and 0 `virtual_camera` recordings so far.
- **Live swaps do not reach HUMAN_REVIEW.** Of the 5 latest live-swap recordings: 4 RETRY_STEP_UP (light too noisy, or the
  camera under 12 fps so `turn.follow` abstained) and **1 PASS** (a false accept). Fusion rule under discussion in #61.
- **No phone tested end to end** (Y0, Y7).
- **SBI weights not installed**, so family D's detector never votes.
- **Open contract and fusion tickets:** #58–#63.
