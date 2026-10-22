# Architecture: adaptive, camera-first liveness for video-KYC

This is the final reference architecture from the team's deck (slide 17, "Detailed reference architecture"). The task lists implement it; when in doubt, this file says what the system is for.

## The idea in two questions

PulseLens asks two separate questions on every V-CIP call, instead of one vague "deepfake score":

1. **Is this a real camera, in this session?** (capture and injection integrity)
   - **Threats:** a pre-recorded replay, a virtual camera (OBS), an injected or re-timed stream.
   - **Evidence:** session binding, frame timing and duplicates, the response to a fresh challenge.
2. **Is the face itself real?** (live manipulation)
   - **Threat:** a real person on a real camera, with the face swapped in real time (Deep-Live-Cam, FaceFusion).
   - **Evidence:** how the face, neck and background respond to our light, head-turn consistency, a visual detector.

A clean camera result does not prove a genuine face, and a weak sensor signal does not prove injection.

**What is ours** (each signal has prior art: Face Flashing, active illumination, self-blended-image detectors): the combination of
- quality-aware fusion,
- adaptive capture,
- testing on Indian devices.

**Principles:**
- **A fresh light challenge per call:** a random colour order and timing, bound to a one-use session nonce. A replayed clip can't know it.
- **Relative, not absolute:** the face is compared with the neck and background in the same session, not with fixed pixel cut-offs.
- **Abstain, don't accuse:** every check reports its own quality. Poor capture leads to a retry, never a fraud flag.
- **Adapt to the measured device:** tests follow the measured frame rate, blur, light and camera support, never the device name.
- **Human-led outcome:** plain-language reasons for the V-CIP agent. PulseLens recommends; the bank decides.

## Three columns

```
 APPLICANT DEVICE                PULSELENS SERVICE (bank VPC / on-prem)                       BANK SYSTEMS
 ────────────────                ─────────────────────────────────────                        ────────────
 Capture SDK          ────────►  1 Session orchestrator & challenge planner                   Bank policy & integration
 Quality preflight     ─ ─ ─ ─►  2 Ingest, provenance & frame integrity          ─────────►  Evidence record (protected)
 Adaptive capture modes ─ ─ ─►   3 Quality gate (per signal, per window)                      Agent review console (human decides)
 Privacy boundary                ┌──────────┬──────────┬──────────┬──────────┐                Case / audit workflow (mocked)
 Device-local limits             │A Pulse   │B Sensor &│C Active  │D Visual &│                India readiness & evaluation
                                 │coherence │lens      │light     │motion    │
                                 │(optional)│physics   │challenge │consistency│
                                 └──────────┴──────────┴──────────┴──────────┘
                                 4 Evidence fusion (quality-aware, not raw-threshold stacking)
                                 5 Policy outcomes: PASS · RETRY / STEP-UP · HUMAN REVIEW
```

**Data boundaries:**
- Capture features cross over the encrypted session channel.
- A raw pulse waveform and a heart rate are never stored.
- Decisions run only server-side.
- Data stays in the bank's environment in India.

## Applicant device (Yash)

- **Capture SDK:**
  - camera frames with monotonic timestamps;
  - face tracking and skin-region landmarks;
  - the screen-colour challenge rendered in-session;
  - uploads only session-scoped capture data.
- **Quality preflight:** measures fps, dropped frames and blur; estimates motion, brightness and clipping; checks the supported camera controls.
  - Camera-control support is not proof of trust.
  - Unsupported means unsupported, never failed.
- **Adaptive capture modes:**

  | Mode | Typical device | What runs |
  |---|---|---|
  | **CAPABLE** | Chrome on Android or desktop, steady frame rate, decent light | full challenge suite: light + turn |
  | **CONSTRAINED** | budget phone, old webcam, iOS Safari, tube-light flicker | a simpler, longer challenge, or the light dropped below 12 fps; turn |
  | **NO-FLASH** (assisted) | photosensitivity, bright sunlight, persons with disabilities | turn + agent-led questions; branch or correspondent route if still short |

  - Capability mode and attack risk are separate: **the mode is never a risk label.**
  - The planner can downgrade mid-session.
- **Privacy boundary:**
  - no stored heart-rate history or raw pulse;
  - temporary frames and metadata minimised;
  - consent and the bank's retention policy;
  - the fraud score is never shown to the applicant.
- **Device-local limits:**
  - camera APIs differ by browser and OS; torch, ISO and white balance may be absent;
  - never fail a customer only for unsupported controls or low signal quality;
  - use screen illumination where feasible.

**Camera controls a web page can actually use** (W3C Image Capture status):

| Browser | Controls exposed to web pages |
|---|---|
| Chrome on Android | exposure, white balance, ISO, focus, zoom |
| Chrome on desktop | exposure and white balance, varying by OS and camera |
| Safari on iOS | limited and version-dependent |
| Firefox | none by default |

The preflight probes the real support live.

## PulseLens service

1. **Session orchestrator & challenge planner (Keshav):**
   - creates a single-use session ID and nonce;
   - selects a randomised colour order and timing, and records the expected events server-side;
   - chooses tests from the measured capture capabilities and quality, not from the device name or declared model.
2. **Ingest, provenance & frame integrity (Keshav):**
   - validates session binding, timestamps, ordering, duplicate frames and upload integrity;
   - tracks observed-vs-requested camera behaviour only where the client API gives trustworthy observations;
   - a hard protocol violation and a weak physical cue get separate reason codes.
3. **Quality gate, per signal and per window (Ganeev):** usable pixels, face and neck visibility, blur, motion, flicker, exposure stability, signal confidence. Low quality means the test abstains and is not counted as attack evidence.

**Four detection families (Ganeev).** Every family returns continuous features, quality, uncertainty, a status (usable · abstain · protocol error) and reason codes.

| Family | Status | Tests | Limit |
|---|---|---|---|
| **A · Pulse coherence** | OPTIONAL | POS/CHROM rPPG from 5 face regions and the neck, if visible. Temporal and spatial consistency, SNR and stability. Continuous similarity features plus uncertainty. Never require a pulse to pass. | Live swaps can inherit the source's pulse (Seibold 2025); low fps, motion and dim light degrade the signal. Logged only, outside the vote, until it adds measured value. |
| **B · Sensor & lens physics** | CORE | Frame cadence, timestamp jitter, dropped and repeated frames. Noise residual and sharpness compared across face, neck and background. Camera mode and exposure response where measurable. PRNU as supporting evidence only. | PRNU is not proof of a physical sensor; compression and browser scaling weaken it. |
| **C · Active camera / light challenge** | CORE + EXPERIMENT | A fresh random screen-colour sequence, tied to the server nonce and timestamps. Response shape, order and lag for face, neck and background. Optional exposure, white-balance or torch probes only when supported. Split-screen illumination is a research extension. | Weak in bright sunlight. A live swap receives a genuinely lit frame and may keep part of the response, so face vs neck is **a hypothesis we test**. Low-fps browsers can't resolve 50 Hz lamp flicker; it is treated as instability with reduced confidence. |
| **D · Visual & motion consistency** | CORE + MODEL | A pretrained face-manipulation detector (SBI) as one feature family. A randomised left or right head turn, tracking landmarks and identity. Temporal blending, boundary and texture consistency across the turn. Close/far motion is optional. | Benchmark-trained detectors may not transfer to Indian device streams. Do not rely on hand occlusion: a masked swap tool handled it (Firc et al. 2026). |

4. **Evidence fusion, quality-aware, not raw-threshold stacking (Keshav):**
   - each family emits continuous features, quality, uncertainty, the evidence direction, reason codes and the family id;
   - challenge responses are normalised against the session baseline;
   - calibration is done across device and lighting cohorts when there is enough data;
   - correlated failures are not double-counted;
   - interpretable weighted evidence comes first; calibrated logistic fusion only with enough person-disjoint data.
5. **Policy outcomes (Keshav):**

   | Outcome | When |
   |---|---|
   | **PASS** | sufficient usable evidence and low estimated risk at the tested operating point |
   | **RETRY / STEP-UP** | poor capture or inconclusive evidence. Options: a fresh challenge, the no-flash path, agent-led checks, assisted KYC |
   | **HUMAN REVIEW** | multiple reliable, distinct families raise risk, or stream integrity is violated. An agent reviews before activation |

   The exact rules are in `docs/CONTRACT.md` §8.

**Never a fraud flag on its own** (these lower confidence or trigger a retry): unsupported camera controls, a low frame rate, dim light, a darker skin tone, no visible neck, a budget device.

## Bank systems

- **Bank policy & integration** (existing):
  - the V-CIP SDK, web app hook and REST risk API;
  - the bank configures permitted actions and retention;
  - PulseLens recommends; bank workflow controls hold;
  - the operating point is set per product (stricter for an instant loan than for a savings account).
- **Evidence record** (protected, Keshav):
  - the session ID, challenge events and time integrity;
  - per-family results, quality, abstentions and reasons;
  - minimised evidence references, encrypted storage, hash-linked audit events.
- **Agent review console** (Keshav):
  - plain-language reasons; failed and abstained shown separately;
  - the review challenge timeline and selected evidence;
  - approve / request re-verification / escalate;
  - never labels inconclusive capture as confirmed fraud.
- **Case / audit workflow:** mocked for the hackathon; protected audit log; role-based access; escalation follows bank procedure and applicable rules.
- **India readiness & evaluation** (Keshav for eval, everyone for recording):
  - **Devices:** budget Android, laptop webcams and browsers.
  - **Conditions:** indoor daylight, dim light, tube-light or LED flicker, multiple skin tones, neck visibility and clothing.
  - **Languages:** English + Hindi coaching first; a Punjabi stretch goal.
  - **What we report:**
    - APCER/BPCER (ISO/IEC 30107-3), with injection reported separately (CEN/TS 18099);
    - abstention, retry rate and latency;
    - all per device, lighting and skin-tone subgroup;
    - person-disjoint splits; one attack tool held out when feasible.
  - Small demo samples are feasibility evidence only, never production accuracy.

## What a session looks like

```
Customer joins the bank's video-KYC call  →  bank asks PulseLens for a session (one-use id + nonce)
→ notice + no-flash option  →  camera permission
→ preflight (~3 s: fps, drops, blur, brightness, controls, face, mode probe) + coaching
→ planner picks CAPABLE / CONSTRAINED / NO-FLASH and a random colour order + turn direction (logged server-side)
→ challenge plays (~15–20 s): neutral baseline, colour steps, "turn your head left/right and back"
→ frames + timestamps + challenge events uploaded, bound to the session
→ integrity → quality gate → families A–D → fusion → PASS / RETRY / HUMAN REVIEW
→ the customer sees only "continue" / "please retry" / "please wait"; the agent sees the reasons and decides
→ evidence record saved (hash-chained)
```

## Security controls (prototype vs production)

| Prototype (built in 48 h) | Production (not in scope; say so if asked) |
|---|---|
| single-use nonce and challenge; session-bound tokens; customer payloads without scores; agent passcode; hash-chained audit events; data under `data/`, demo sessions purged after 1 h | TLS end to end (RBI device-to-host encryption); role-based reviewer access; encryption at rest; native-app attestation against injection; licensed detector weights (SBI weights are research-only); patent check (challenge-response liveness is heavily patented, e.g. US 12,413,865); security audit |
