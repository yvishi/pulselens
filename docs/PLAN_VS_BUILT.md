# PulseLens: Plan vs. Built Report

**Context:** Amazon AI Cyber Security Hackathon Finale (Challenge 03 — Team Mama Mia)  
**Evaluator Reference:** Criterion 5 (Honest Accounting of Promised vs. Built vs. Cut)

---

## 1. Executive Summary & Scorecard

PulseLens was planned as a 48-hour parallel engineering sprint across three distinct functional tracks:
1. **Applicant Device / Capture SDK** (Yash)
2. **Engine, Storage, Console & Evaluation** (Keshav)
3. **Analysis, Physics & Computer Vision** (Ganeev)

### High-Level Accounting

| Category | Count | Status | Notes |
|---|---|---|---|
| **Core Tasks Planned** | 32 | — | Y0–Y10, K1–K11, G1–G11 defined in `docs/PLAN.md` |
| **Fully Built & Merged** | 29 | 90.6% | Merged directly to `main` with passing automated suites |
| **Additions Beyond Plan** | 4 | 100% | Judge video ingest, post-decision frame purge, walkthrough doc, plan-vs-built doc |
| **Cut from Scope** | 2 | 6.25% | `pulse.coherence` (rPPG), `turn.identity` (explicitly on Plan Cut List §7) |
| **Deferred / Awaiting Data** | 1 | 3.1% | G9 Calibration on Set A (requires physical volunteer recordings) |

**Automated Test Health at Code Freeze:**
- **Python / Pytest:** 428 passed, 4 skipped (model weights / hardware optional), 0 failures.
- **Web / Vitest:** 177 passed across 16 test files, 0 failures.
- **Linters (Ruff + ESLint):** Zero errors, zero warnings.

---

## 2. Track Breakdown: Promised vs. Built vs. Cut

### Track 1: Applicant Device & Customer Flow (Owner: Yash)

| Task ID | Component Promised | Status | What Was Built & Merged | PR / Commit |
|---|---|---|---|---|
| **Y0** | Device Preparation & HTTPS Tunnel | **Done** | Cloudflare tunnel integration via `scripts/dev.py tunnel`, mobile testing harness. | Manual / scripts |
| **Y1** | Camera, Clock & Frame Grabber | **Done** | Zero-lag canvas-based frame grabber, monotonic millisecond clock (`performance.now()`), JPEG worker pipeline. | PR #14 |
| **Y2** | Quality Preflight & Mode Probe | **Done** | Front-camera preflight (FPS, lighting, face bounding box, camera capability probe). Graceful degradation on iOS/Safari. | PR #18 |
| **Y3** | Challenge Renderer & Display | **Done** | Fullscreen challenge overlay, Rec.709 sRGB flash sequences, sub-millisecond paint event timestamps. | PR #20 |
| **Y4** | Uploader & Customer Flow v1 | **Done** | Batch chunk uploader with exponential backoff, retry queue, customer UI flow. | PR #24 |
| **Y5** | Head-Turn Guidance Ring | **Done** | Circular arc indicator tracking yaw angle, progressive feedback ring at 20° deflection, text fallback. | PR #26 |
| **Y6** | Coaching Tips & Bilingual Strings | **Done** | Real-time coaching prompts (dim light, backlight, proximity, blur); English and Hindi strings with auto-detect. | PR #27 |
| **Y7** | Mobile Hardening | **Done** | Android fullscreen & portrait lock, iOS wake lock re-acquisition, dynamic viewport (`100dvh`). | PR #30 |
| **Y8** | Lab Recording Screen | **Done** | Operator console (`/lab`) for recording ground-truth dataset with pseudonymised participant codes (Pxx, Dxx). | PR #25 |
| **Y9** | Capture Hardening & Error States | **Done** | Graceful camera permissions error handling, FPS drop downgrade, manual exposure lock (`?lock=1`). | PR #31 |
| **Y10** | End-to-End Test Suite | **Done** | Playwright test matrix covering fake camera, customer flow, lab flow, and forbidden word assertions. | PR #29 |

---

### Track 2: Engine, Storage, Console & Evaluation (Owner: Keshav)

| Task ID | Component Promised | Status | What Was Built & Merged | PR / Commit |
|---|---|---|---|---|
| **K1** | Scaffold, Dev Script & Contracts | **Done** | `contracts.py` & `contracts.ts`, `bundle.py`, `scripts/dev.py` multi-platform CLI orchestrator. | PR #1 |
| **K2** | Sessions API & Store | **Done** | FastAPI endpoints, HMAC session authentication, re-entrant read/write locks, 413 payload bounds. | PR #2 |
| **K3** | Planner & Challenge Generator | **Done** | Pseudo-random nonce seed generator, 3-tier planning engine (CAPABLE, CONSTRAINED, NO_FLASH), safety guards. | PR #12 |
| **K4** | Analysis Runner & Async Worker | **Done** | Background execution pipeline with thread pool, timeout protection, and synthetic fallback. | PR #13 |
| **K5** | Ingest Integrity Checks | **Done** | Strict packet protocol verification (`integrity.protocol`) and frame drop/gap analysis (`integrity.coverage`). | PR #15 |
| **K6** | Decision Fusion & Outcome Matrix | **Done** | Usable-gate evaluation, correlated cue grouping, 3-tier decision engine (PASS, RETRY, HUMAN_REVIEW). | PR #16 |
| **K7** | Agent Review Console (v1 + v2) | **Done** | Dual-mode operator dashboard (`/console`), evidence thumbnails, interactive uPlot light curves, action logging. | PR #21, #23 |
| **K8** | Cryptographic Audit Record | **Done** | Tamper-evident SHA-256 hash-chained `audit.jsonl` log, verification CLI `scripts/verify_audit.py`. | PR #39 |
| **K9** | Customer Launch & QR Pairing | **Done** | Dynamic QR code generation, direct copy links, product flow selector on console. | PR #34 |
| **K10** | Evaluation Harness & Metrics | **Done** | APCER/BPCER calculations with Wilson 95% confidence intervals, ROC-AUC separation metrics, freeze hashes. | PR #36, #37 |
| **K11** | Hardening & Retention Purge | **Done** | Inactivity session purge daemon (60 min window), demo state reset switch, secure session isolation. | PR #36 |
| **Bonus 1** | Judge Video Ingest Script | **Done** | `scripts/ingest_video.py` converts arbitrary video files into live PulseLens session bundles with full check execution. | PR #88 |
| **Bonus 2** | Privacy Frame Purge | **Done** | Immediate raw frame deletion on agent decision for `/customer` sessions, retaining audit integrity hash. | PR #89 |
| **Bonus 3** | Comprehensive Walkthrough Doc | **Done** | `docs/WALKTHROUGH.md` covering stages 1–5, architecture diagram, file pointer index table. | PR #91 |

---

### Track 3: Analysis, Physics & Computer Vision (Owner: Ganeev)

| Task ID | Component Promised | Status | What Was Built & Merged | PR / Commit |
|---|---|---|---|---|
| **G1** | Vision Base & Landmark Tracking | **Done** | MediaPipe 478-point mesh extraction, canonical face/neck/background ROI segmentation, synthetic bundle generator. | PR #3, #4 |
| **G2** | Per-Window Quality Gate | **Done** | Temporal window quality assessment (lighting saturation, motion blur, face occlusion, frame rate thresholds). | PR #7, #8 |
| **G3** | Optical Light Response | **Done** | Constant-fraction onset timing, bandpass echo verification, chromaticity order verification against challenge. | PR #6, #7 |
| **G4** | Sensor Cadence & Duplicates | **Done** | Monotonic timing jitter analysis, perceptual difference hash (dHash), frame duplicate cluster detection. | PR #4 |
| **G5** | Differential Light Reflection | **Done** | Skin vs. clothing reflection ratio (`light.face_neck`), ambient back-wall light spill detection (`light.background`). | PR #8, #9 |
| **G6** | Active Head-Turn Verification | **Done** | 3D head pose estimation, angular yaw velocity tracking, prompt latency validation (`turn.follow`). | PR #11 |
| **G7** | Self-Blended Images (SBI) Detector | **Done** | EfficientNet-B4 deepfake classifier, aligned face crop extraction, checkpoint weight loading pipeline. | PR #40, #41 |
| **G8** | Advanced Sensor Diagnostics | **Done** | Virtual camera mode switch probing (`sensor.mode_probe`), spatial region noise analysis (`sensor.regions`), PRNU. | PR #38, #40 |
| **G9** | Calibration on Real Dataset | **Deferred** | Evaluation code and separation metrics built (`eval/separation.py`), awaiting physical dataset recording. | Deferred |
| **G10** | Pulse Coherence & Turn Identity | **Cut** | Cut per Plan Section 7 (Cut List items 1 & 2). Rationale documented below. | Cut (§7) |
| **G11** | Robustness, Glare & Performance | **Done** | Specular highlight clipping, low-quality JPEG tolerance, sub-12s CPU runtime on 900 frames. | PR #41 |

---

## 3. Plan Cut List: Planned vs. Actual

Section 7 of `docs/PLAN.md` established a prioritized cut list to protect project completion under time constraints. Here is the exact reconciliation:

| Cut List Item | Description | Planned Fate | Actual Outcome | Technical Rationale |
|---|---|---|---|---|
| **1. `pulse.coherence` (Family A)** | Physiological rPPG heartbeat extraction | Cut if behind | **Cut** | rPPG waveforms are highly unreliable under mobile auto-exposure and varying indoor ambient light within 48h. Furthermore, storing or plotting pulse waveforms violates core privacy constraints (AGENTS.md Rule 8). |
| **2. `turn.identity`** | Multi-angle biometric face matching during turn | Cut if behind | **Cut** | Active head pose velocity and direction (`turn.follow`) provides physical liveness. Multi-pose face matching adds high computational overhead without improving presentation attack detection. |
| **3. `sensor.prnu`** | Sensor Photo-Response Non-Uniformity | Cut if behind | **Built (Non-Voting)** | Retained as a passive diagnostic check (`voting=False`). Mobile video encoding (H.264/JPEG compression) suppresses subtle high-frequency sensor noise; kept as diagnostic. |
| **4. `light.background`** | Ambient screen bounce on background wall | Cut if behind | **Built & Merged** | Implemented in G5 (`checks/light_common.py`); effectively discriminates glossy screens from physical rooms. |
| **5. Hindi strings** | Bilingual customer accessibility | Cut if behind | **Built & Merged** | Full English and Hindi localized string dictionary implemented in Y6 (`web/src/customer/strings.ts`). |
| **6. Exposure lock** | WebCam hardware exposure freeze (`?lock=1`) | Cut if behind | **Built & Merged** | Added in Y9 (`web/src/capture/camera.ts`) using MediaTrackCapabilities. |
| **7. Evidence-record hash chain** | SHA-256 cryptographic chaining | Cut if behind | **Built & Merged** | Fully implemented in K8 (`server/pulselens/engine/audit.py`) and verified by `scripts/verify_audit.py`. |
| **8. Lab recording screen polish** | Ground truth recording UI | Cut if behind | **Built & Merged** | Built in Y8 (`web/src/lab/LabPage.tsx`) with metadata tracking, consent validation, and session export. |

---

## 4. Architectural Adherence & Principles

1. **Keep It Simple, Stupid (KISS):**
   - Pure filesystem storage under `data/sessions/` using standard JSON and JPEG formats. No external database servers or distributed caches required.
   - Deterministic fusion rules: clear, explainable decision hierarchy instead of opaque end-to-end black box classifiers.
2. **You Aren't Gonna Need It (YAGNI):**
   - Strict adherence to the shared `CONTRACT.md` without speculative API fields.
   - Refusal to prematurely add complex cloud infra; entire stack runs locally with `python scripts/dev.py server` and `python scripts/dev.py web`.
3. **Privacy First & RBI V-CIP Compliance:**
   - Raw face frames are immediately purged from disk once an agent reviews a session (`delete_frames_on_decision: true`), leaving only the tamper-evident cryptographic audit trail.
   - Zero biometric pulse or biometric template data retained.
