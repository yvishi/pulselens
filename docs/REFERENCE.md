# Reference: the old prototype, measured facts and sources

## The old repo

The team's first prototype is at `https://github.com/GTsingh600/PulseLensFinal` (branch `main`). It was built to an older design, but much of its capture and analysis code is tested and directly reusable.

```bash
git clone https://github.com/GTsingh600/PulseLensFinal.git ../PulseLensFinal-ref
```

**How to use it:**
- Read, port and simplify into **your own paths** in this repo, with fresh tests.
- Don't copy its structure: it has six families, five routes, two sites and an explainer system. This repo has four families, three outcomes, one web app and plain-language explanations.
- Each task list has a port table naming the exact old files.

**Useful old docs:**

| File | Why |
|---|---|
| `docs/STATUS.md` | every measured number and decision, with session ids |
| `docs/research/live_swaps_and_detectors.md` | what a live swap can't fake, prebuilt detectors, active probes |
| `docs/research/pulse_and_illumination.md` | multi-site pulse, screen illumination, rules vs learning |
| `docs/research/deck_review.md` | why "the face lags the neck" was dropped |
| `server/pulselens/calibration/bootstrap.yaml` | the provisional thresholds with their reasoning |
| `playwright.config.ts`, `e2e/replay.spec.ts`, `scripts/bundle_to_y4m.py` | fake camera and replay-attack e2e |

## Facts measured on the old prototype

All on about 7 genuine sessions, one person, one laptop webcam, plus a replay and Chromium's fake camera. **Treat them as hypotheses, not results.**

| Fact | Numbers | What it means for this build |
|---|---|---|
| Chromium's fake camera vs the real webcam in the mode probe | the fake camera accepted an unusual 1000×750 mode and switched in 57–105 ms with 0 dropped frames; the real webcam refused it | `sensor.mode_probe` (G8) is promising against injected streams; OBS is untested |
| Replay of a genuine session | every camera check passed it (PRNU PCE 7542); the light echo answered **0 of 6** flashes | the light challenge (C) is what catches replays; B alone does not |
| Laptop webcam, bright room | 15.6 fps; face echo near the noise floor (SNR ≈ 5) | desktop light echoes are weak in bright rooms; prefer full-screen colour |
| Same webcam, dim room | echo 3–6× stronger (SNR 15–30) but the camera fell to **10.4 fps**, below the 12 fps floor | dim rooms push webcams into CONSTRAINED (no light); the exposure lock at 33 ms when fps < 27 was added but **not confirmed** |
| One webcam frame | 64–96 ms | timing lag between face and neck can't be resolved; compare echo **strength and colour direction** |
| Sensor fingerprint (PRNU) | genuine sessions as low as PCE 174; Chromium's fake camera produced a stable PCE 97 | PRNU is supporting evidence only (limit 50); never flag on it |
| Face vs neck with a darker, exposure-locked picture | the face threshold rose and "below threshold" was misread as silence | "silent" needs a threshold able to hear a quarter of the neck's echo; else the step is unclear |
| Neck in frame on a laptop | 41% of the neck box in frame in one session | coach "show your shoulders"; abstain when neck coverage < 0.5 |

**Not measured at all yet:**
- any phone;
- OBS or any real virtual camera;
- **any live face swap**;
- tube lights;
- skin tones beyond one person;
- Hindi coaching.

## The deck (final), in one page

- **Problem:**
  - deepfakes get into video-KYC: a harvested face, plus leaked Aadhaar/PAN, a real-time swap on a consumer GPU, and injection through a virtual camera or a replay;
  - genuine users get held back (budget phones, old webcams, dim rooms, tube lights, slow networks; browsers differ);
  - since 2025, liveness may not rely on blinking alone or exclude persons with disabilities.
  - **Numbers:**
    - ₹19,813 cr lost to online fraud in India in 2025 (I4C);
    - the MHA/I4C advisory of June 2026 says deepfakes can bypass Video-KYC;
    - RBI KYC Master Direction §18 requires liveness and spoof detection.
- **Approach:** two questions, four families, three outcomes, the agent decides (see `docs/ARCHITECTURE.md`).
- **Fusion:** "threshold-light". Each check returns continuous evidence; few calibrated cut-points; gate → normalise → group → combine (interpretable table) → calibrate (later, only with enough person-disjoint data).
- **Console** (deck slide 9, an illustrative mock-up):
  - header "V-CIP session VK-20817 · Instant personal loan";
  - the challenge timeline;
  - "Plan used: Capable mode, desktop Chrome, good light. Exposure probe: unsupported on this camera, so recorded as unsupported, not failed.";
  - evidence by family: B FLAG "irregular frame cadence; runs of near-duplicate frames", C FLAG "face matched 1 of 6 colour steps; wrong order", D NOT RAISED "turn completed; detector below review level", A ABSTAINED "signal quality too low";
  - the HUMAN REVIEW banner "Two distinct families raise risk … Replay or injection suspected; not a fraud finding.";
  - buttons Approve / Re-verify / Escalate to fraud;
  - side notes: "Failed vs abstained shown separately", "Evidence on a timeline", "Nothing for attackers to learn".
- **Deployment story:**
  - Phase 0 shadow mode → Phase 1 agent assist on instant-loan calls → Phase 2 all account opening → Phase 3 re-KYC and recovery;
  - integrates as a JavaScript capture SDK in the existing V-CIP web call plus a REST risk API;
  - the bank's own cloud or on-prem;
  - target friction under 20 s, to be measured.
- **Live demo:** 4 scenarios (see `docs/PLAN.md` section 6).
- **Attack lab:** a phone-screen replay, a pre-recorded clip via the OBS virtual camera, live swaps (Deep-Live-Cam, FaceFusion) and a photo-animated clip (LivePortrait); consenting teammates only.
- **Reporting:** counts with denominators per device and lighting group, failed and abstained separately.

## Sources

1. Gerstner & Farid, Detecting Real-Time Deep-Fake Videos Using Active Illumination, CVPRW 2022.
2. Tang et al., Face Flashing, NDSS 2018 (arXiv 1801.01949).
3. An et al., Facial and neck region rPPG similarity for deepfake detection, IET Biometrics 2024.
4. Seibold et al., "High-quality deepfakes have a heart!", Frontiers in Imaging 2025: swaps inherit the driver's pulse (median r = 0.89 for DeepFaceLive).
5. Shiohara & Yamasaki, Detecting Deepfakes with Self-Blended Images, CVPR 2022 (github.com/mapooon/SelfBlendedImages).
6. Firc et al., Not All Challenges Are Equal, arXiv 2610.16417 (Oct 2026): head-pose challenges scored best; hand occlusion was weakest against a masked swap tool.
7. Nowara et al., Impact of skin tone and gender on camera-based PPG, CVPRW 2020.
8. ISO/IEC 30107-3:2023 (APCER/BPCER).
9. CEN/TS 18099:2024 (injection attack detection).
10. W3C Image Capture implementation status (github.com/w3c/mediacapture-image).
11. WCAG 2.3.1 (three flashes or below threshold).
