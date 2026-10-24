# PulseLens: End-to-End Technical Walkthrough

A one-page technical guide through the PulseLens verification pipeline: from camera input to tamper-evident audit logging, multimodal quality-gated checks, evidence fusion, and human-agent review.

---

## 1. Pipeline Architecture

```
[Applicant Device / Video]
       │
       ▼ (W3C camera probe, preflight, adaptive mode, single-use nonce)
[Capture & Ingest] ──► [Service Step 2: Integrity & Audit]
                             │
                             ├─► SHA-256 Hash-Chained Audit Log (`audit.jsonl`)
                             │
                             ▼
               [Step 3: Quality Gate Per Window]
                             │
       ┌─────────────────────┼─────────────────────┬─────────────────────┐
       ▼                     ▼                     ▼                     ▼
[Family A: Pulse]     [Family B: Sensor]    [Family C: Light]     [Family D: Motion]
(Experimental)        (Cadence, Dups, PRNU) (Echo, Neck, Wall)    (Head turn, SBI)
       │                     │                     │                     │
       └─────────────────────┼─────────────────────┴─────────────────────┘
                             ▼
             [Step 4: Evidence Fusion & Policy]
                             │
                             ▼
        [Step 5: Agent Console & Privacy Purge]
        (Approve / Re-verify / Escalate ──► Purge Raw Frames)
```

---

## 2. Walkthrough by Stage

### Stage 1: Applicant Capture & Adaptive Preflight
- **Code:** `web/src/capture/camera.ts`, `preflight.ts`, `probe.ts`, `coaching.ts`, `flash.ts`
- **Fallback Ingest:** `scripts/ingest_video.py` (reads arbitrary video file into a session bundle for judging).
- **Protocol:**
  1. **One Clock Rule:** Client times use `performance.now()` relative to challenge start $t_0$, never `Date.now()`.
  2. **Hardware Probe:** Tests real W3C Image Capture controls (exposure mode, ISO, white balance, zoom) and resolution switching. Unsupported controls abstain gracefully, never flag.
  3. **Adaptive Mode Selection:** Planner (`server/pulselens/engine/planner.py`) assigns `CAPABLE` ($\ge 20$ fps), `CONSTRAINED` ($12\text{--}19$ fps), or `NO_FLASH` ($< 12$ fps, dark/bright extremes, or photosensitivity toggle). Mode is capability-only, never a fraud score.
  4. **Active Challenge:** Screen renders randomized hue sequence ($c_0\dots c_n$, no red band to protect photosensitive users) and head-turn direction prompt ($t_0$).

### Stage 2: Ingest Provenance & Hash-Chained Integrity
- **Code:** `server/pulselens/api/sessions.py`, `server/pulselens/engine/integrity.py`, `server/pulselens/engine/store.py`, `server/pulselens/engine/audit.py`
- **Integrity Validation:**
  - `integrity.protocol`: Checks strictly monotonic timestamps, non-duplicate frame indices, adherence to challenge event order, and prevents post-completion submissions (`integrity.after_complete`).
  - `integrity.coverage`: Requires $\ge 50$ frames and $< 20\%$ upload batch gap rate. Missing batches flag network drops rather than spoofing.
- **Tamper-Evident Audit Chain:**
  - Every session action (`session.created`, `challenge.issued`, `frames.batch`, `events.received`, `analysis.done`, `decision.made`, `agent.action`, `frames.deleted`) appends a hash-linked line to `audit.jsonl`.
  - Formula: $\text{hash}_i = \text{SHA256}(\text{hash}_{i-1} + \text{canonical\_json}(\text{line}_i))$.
  - Verified offline via `python scripts/verify_audit.py data/sessions/<id>`.

### Stage 3: Multimodal Quality-Gated Analysis
- **Quality Gate:** `server/pulselens/analysis/quality.py` (`assess()`, `WindowQuality`).
  - Evaluates luma, overexposure/clipping, inter-frame motion, and neck presence for each temporal window.
  - Substandard windows abstain (`status="abstain"`). Bad capture triggers retry, never fraud flags.
- **Family A (Pulse Coherence):** `pulse_coherence.py`. Experimental rPPG cardiac sync. Evaluated and displayed; explicitly non-voting in decision policy.
- **Family B (Sensor & Lens Physics):**
  - `sensor_stream.py`: Inter-frame timestamp cadence coefficient of variation (`sensor.cadence`) and duplicate dHash detection (`sensor.duplicates`). Catches frame freezes and virtual camera streaming loops.
  - `sensor_probe.py`: Hardware mode switch latency and dropped frame verification (`sensor.mode_probe`).
  - `sensor_regions.py`: Spatial noise difference across sensor regions (`sensor.regions`).
  - `sensor_prnu.py`: Photo-Response Non-Uniformity sensor fingerprint consistency (`sensor.prnu`).
- **Family C (Active Light Challenge):**
  - `light_response.py`: Constant-fraction onset delay and chromaticity delta projection against challenge hues (`light.response`). Recorded replays and deepfakes cannot predict nonce-randomized screen pulses and honestly report `light.no_echo`.
  - `light_face_neck.py`: Relative face-to-neck reflectance ratio (`light.face_neck`). Detects physical masks and deepfake face-swap boundary cutouts.
  - `light_background.py`: Wall/background light reflection comparison (`light.background`).
- **Family D (Visual & Motion Consistency):**
  - `turn_follow.py`: 3D landmark head yaw latency, direction tracking, and return consistency (`turn.follow`).
  - `visual_sbi.py`: Self-Blended Images artifact detector for synthetic blending boundaries (`visual.sbi`).

### Stage 4: Quality-Aware Evidence Fusion
- **Code:** `server/pulselens/engine/fusion.py`, `server/pulselens/engine/reason_text.py`
- **Rules:**
  1. **Usable Gate:** Only `status="usable"` checks enter voting; abstained checks contribute zero attack weight.
  2. **Correlated Cue Collapsing:** Signals within identical `vote_group`s collapse to a single vote.
  3. **Decision Hierarchy:**
     - **HUMAN REVIEW (Red):** Integrity violation or flags across $\ge 2$ independent families (e.g. Family B virtual camera + Family C light failure).
     - **RETRY / STEP-UP (Amber):** Single-family flag or low signal coverage. Generates specific next step: `fresh_challenge` (retry), `no_flash` (photosensitive/dim), `agent_checks` (manual agent question prompt), or `assisted_kyc` (in-person branch referral).
     - **PASS (Green):** Sufficient coverage with zero flagged families.

### Stage 5: Agent Console & Privacy Safeguards
- **Code:** `web/src/console/ConsoleSession.tsx`, `FamilyCard.tsx`, `EvidenceFrames.tsx`, `AgentActions.tsx`, `server/pulselens/api/agent.py`
- **Workflow:**
  - Password-gated console (`X-Agent-Passcode`). Polling updates session state in real-time.
  - Displays: plan rationale, challenge timeline with requested vs painted markers, expandable family cards with uPlot feature charts, and thumbnail evidence frames.
  - Action buttons: **Approve**, **Re-verify** (creates attempt $N+1$ link + QR code), or **Escalate** to fraud.
  - **Running Privacy Safeguard (Criterion 4):** Once the agent submits an action on customer sessions, `SessionStore.record_agent()` permanently deletes raw biometric frames (`folder/frames/*.jpg`) and writes `frames.deleted` to the hash chain. Stored results, audit log, and decision records remain intact.

---

## 3. Key File Pointer Index

| Stage | Component | Path | Responsibility |
|---|---|---|---|
| Capture | Camera & Probe | `web/src/capture/camera.ts`, `probe.ts` | W3C camera control probing & frame acquisition |
| Capture | Preflight | `web/src/capture/preflight.ts` | Lighting, motion, blur, and fps evaluation |
| Ingest | Video Fallback | `scripts/ingest_video.py` | Ingest external judge video to session bundle |
| Ingest | Storage & Lock | `server/pulselens/engine/store.py` | Atomic session file management & locking |
| Integrity | Provenance | `server/pulselens/engine/integrity.py` | Protocol rule checks & batch continuity |
| Audit | Evidence Log | `server/pulselens/engine/audit.py`, `scripts/verify_audit.py` | SHA-256 tamper-evident chaining |
| Analysis | Quality Gate | `server/pulselens/analysis/quality.py` | Per-window quality assessment & abstain logic |
| Analysis | Physics / Stream | `server/pulselens/analysis/checks/sensor_stream.py` | Cadence jitter & duplicate frame detection |
| Analysis | Active Illumination | `server/pulselens/analysis/checks/light_response.py` | Chromatic echo response to challenge hues |
| Analysis | Face-vs-Neck | `server/pulselens/analysis/checks/light_face_neck.py` | Relative surface reflectance comparison |
| Analysis | Head Turn | `server/pulselens/analysis/checks/turn_follow.py` | 3D head yaw latency & direction tracking |
| Analysis | SBI Detector | `server/pulselens/analysis/checks/visual_sbi.py` | Self-blended boundary artifact detection |
| Decision | Evidence Fusion | `server/pulselens/engine/fusion.py` | Correlated cue fusion & policy recommendation |
| Review | Agent Console | `web/src/console/ConsoleSession.tsx` | Human-in-the-loop audit & evidence review |
| Privacy | Frame Purge | `server/pulselens/engine/store.py` (`record_agent`) | Post-decision biometric frame deletion |
