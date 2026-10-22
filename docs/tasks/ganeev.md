# Ganeev: analysis, the evidence families A to D (G1 to G11)

**You own:** the analysis behind service step 3 (the quality gate) and the four evidence families. That is the vision base (face, neck and background regions, yaw), every check of families A, B, C and D, the SBI model, the synthetic fixtures, and threshold calibration.

**Your paths:** `server/pulselens/analysis/**`, `server/tests/analysis/**`, `server/tests/fixtures/**`, `server/requirements/analysis.txt`, `scripts/fetch_models.py`, `scripts/calibrate.py`. Never edit `contracts.py`, `bundle.py`, `engine/**` or `api/**` (Keshav's): ask with an issue.

**Before each task:** read CONTRACT §3 (`CheckResult`), §5 (bundle), §6 (analysis interface), §7 (reason codes) and §9 (check catalogue).

**After each task:**
- Run `python scripts/dev.py test` and `lint`.
- Tick the task in `docs/status/ganeev.md`.
- Open a PR and merge it (never delete the branch).

**Rules that bite in your area:**
- **Checks never raise.** Bad, missing or short input → `status: "abstain"`, a `quality` value and reason codes. Wrap every check: an unexpected exception becomes `abstain` with `quality.check_error` (and the traceback in the server log).
- **Abstain is never attack evidence.** `risk` is `None` unless `status == "usable"`; `flag` is false unless usable.
- **Relative, not absolute.** Compare the face with the neck and background of the same session, against the session's own baseline (median, MAD). No absolute colour cut-offs: skin tones vary.
- **Thresholds come only from genuine set A sessions** (G9). Until then every result carries `threshold_source: "provisional"`.
- **Privacy.** Never write a heart rate or a pulse waveform to disk, to `features` or to `plot`.
- **Pure analysis.** Functions take NumPy arrays and dataclasses and return dataclasses. File reading only through `bundle.load_bundle` and the landmarks cache.
- **Tests use synthetic data only.** No real faces in `server/tests`.
- **`explanation`** is one plain sentence with the real numbers, for example "The face answered 5 of 6 colour steps, 120 ms after each (expected 0–300 ms)."

**Port from the old repo** (`../PulseLensFinal-ref/server/`). It is tested; port its logic and tests, renamed to this contract.

| Old file | What to take | New home |
|---|---|---|
| `pulselens/vision/linearize.py` | `srgb_to_linear` | `analysis/vision/linearize.py` |
| `pulselens/vision/face.py` | `Landmarker` (MediaPipe VIDEO mode), `regions_from_landmarks` (skin, cheeks, **neck box**, background), `Box` | `analysis/vision/face.py` |
| `pulselens/vision/frames.py` | `region_means`, `dhash` | `analysis/vision/frames.py` |
| `pulselens/vision/noise.py` | `NoiseAccumulator`, `fit_channel` | `analysis/vision/noise.py` |
| `pulselens/vision/prnu.py` | `residual`, `fingerprint`, `pce` | `analysis/vision/prnu.py` |
| `pulselens/checks/echo.py` | `chromaticity`, `direction`, `echo_onset` (constant-fraction onset, SNR gate) | `analysis/echo.py` |
| `pulselens/checks/optical_light.py` | median onset delay, ≥ 4 valid pulses | `analysis/checks/light_response.py` |
| `pulselens/checks/optical_face_neck.py` | face vs neck, the "unclear vs silent" fix | `analysis/checks/light_face_neck.py` |
| `pulselens/checks/camera_timing.py`, `camera_duplicates.py` | `timing_features`, dHash duplicates | `analysis/checks/sensor_stream.py` |
| `pulselens/checks/camera_modes.py` | the phantom-switch rule | `analysis/checks/sensor_probe.py` |
| `pulselens/calibration/bootstrap.yaml` | provisional values | `analysis/thresholds.yaml` |
| `tests/fixtures/synth.py` | `light_session`, `synthetic_landmarks`, rendering face/neck echoes | `server/tests/fixtures/synth.py` |
| `scripts/fetch_models.py` | MediaPipe model download | `scripts/fetch_models.py` |

**Measured facts to keep in mind:**
- One webcam frame is 64–96 ms, longer than any lag limit. So **compare echo strength and colour direction, not lag**.
- In a dim room the echo was 3–6× stronger, but the camera fell to 10.4 fps.
- Chromium's fake camera produced a stable PRNU pattern (PCE 97), so PRNU is supporting evidence only.

---

## G1. Package skeleton, vision base, analyze(), synthetic bundles, CLI (H0–5)

You can start these files at H0, before K1 merges; they are all yours. You need K1's `contracts.py`/`bundle.py` to run them, so pull `main` at H1.

**Files:**
- `server/requirements/analysis.txt`: `mediapipe` (0.10.x; it brings `opencv-contrib-python`; do **not** add `opencv-python-headless`, which would overwrite the same `cv2`), `scipy`.
- `scripts/fetch_models.py`: downloads `face_landmarker.task` into `models/mediapipe/` (port it).
- `server/pulselens/analysis/__init__.py` (exports `analyze`), `analysis/__main__.py` (the CLI), `analysis/context.py`, `analysis/result.py`, `analysis/reason_text.py`, `analysis/thresholds.yaml`, `analysis/thresholds.py`.
- `analysis/vision/{__init__,linearize,face,frames,pose}.py`.
- `server/tests/fixtures/{__init__,synth.py}`.
- `server/tests/analysis/test_vision.py`, `test_analyze.py`.

**Interfaces you produce:**
```python
# analysis/context.py
@dataclass
class RegionSeries:
    rgb_linear: np.ndarray        # (n_frames, 3) mean linear RGB, NaN where the region is not usable
    coverage: np.ndarray          # (n_frames,) share of the region inside the frame, 0..1

@dataclass
class AnalysisContext:
    bundle: Bundle
    t: np.ndarray                 # (n,) frame t_ms
    regions: dict[str, RegionSeries]   # "skin", "left_cheek", "right_cheek", "neck", "background"
    yaw: np.ndarray               # (n,) degrees, NaN without a face (CONTRACT §1 sign)
    face_box: np.ndarray          # (n, 4) x, y, w, h in pixels, NaN without a face
    quality: "QualityReport"      # from G2
    thresholds: "Thresholds"

def build_context(bundle: Bundle, thresholds: Thresholds) -> AnalysisContext: ...
# Runs the landmarker over every frame in VIDEO mode, at the frame's t_ms, with output_facial_transformation_matrixes=True,
# caching to <bundle>/landmarks.jsonl ({idx, landmarks | null, yaw, pitch}); a present cache is used as-is.

# analysis/result.py
def result(check_id: str, family: Family, vote_group: str, *, risk: float, flag_at: float, quality: float,
           features: dict[str, float], reasons: list[str], explanation: str, source: ThresholdSource,
           window_id: str | None = None, plot: Plot | None = None, uncertainty: float | None = None) -> CheckResult: ...
           # flag = risk >= flag_at; risk is clipped to 0..1
def abstain(check_id: str, family: Family, vote_group: str, reasons: list[str], explanation: str,
            quality: float = 0.0) -> CheckResult: ...
def guarded(fn) -> fn: ...        # decorator: any exception -> abstain("quality.check_error")

# analysis/__init__.py
CHECKS: list[Callable[[AnalysisContext], list[CheckResult]]]   # each G task appends its check here
def analyze(session_dir: Path) -> list[CheckResult]: ...      # CONTRACT §6; never raises

# server/tests/fixtures/synth.py
def make_session(root: Path, *, kind: Literal["genuine", "replay", "swap_no_face_echo", "virtual_camera"] = "genuine",
                 fps: float = 30.0, n_colour: int = 6, turn: Literal["left", "right"] | None = "left",
                 turn_followed: bool = True, noise: float = 0.003, seed: int = 0) -> Path: ...
# Writes a complete bundle through bundle.write_bundle plus landmarks.jsonl, so tests never need the face model.
# Frames are small rendered images (e.g. 160x120) where the face, neck and background boxes take the screen light with
# a delay (genuine 100 ms, face and neck together), with no echo (replay), with neck-only echo (swap_no_face_echo),
# or with perfectly regular timing and zero sensor noise (virtual_camera). Yaw follows the turn step when turn_followed.
```
- **Yaw** from the facial transformation matrix (4×4, column-major): `yaw = degrees(atan2(m[8], m[10]))`. Confirm the sign against Yash's client measurement (both sides must give positive for the person's own left) and note it in your status file.
- **Regions:** port `regions_from_landmarks` exactly; the neck box is 0.6 face widths wide, from 0.05 to 0.45 face heights below the chin, clipped to the frame, with `coverage` = the clipped area / the nominal area.
- **CLI:** `python -m pulselens.analysis <session_dir> [--plots]`:
  - prints a table of `check_id`, family, status, risk, flag and explanation;
  - `--plots` writes PNGs of every `plot` to `<session_dir>/analysis/` (matplotlib; add it to `analysis.txt`).

**Tests:**
- `test_vision.py`:
  - `srgb_to_linear` endpoints (0 → 0, 1 → 1, 0.5 → ≈ 0.214);
  - `regions_from_landmarks` on `synthetic_landmarks()`: the neck box is below the chin and 0.6 face widths wide;
  - a neck box half outside the frame gives coverage ≈ 0.5.
- `test_analyze.py`:
  - `analyze` on a genuine synthetic bundle returns a list of `CheckResult` (valid by pydantic);
  - `analyze` on an empty directory returns abstains and does not raise;
  - `analyze` on a bundle with a corrupt JPEG does not raise.

**Done when:** merged by H5, so Keshav can switch off `PULSE_FAKE_ANALYSIS` for S1.

---

## G2. Quality gate: service step 3 (H4–7)

**Files:**
- `analysis/quality.py`
- `server/tests/analysis/test_quality.py`

**Interfaces:**
```python
@dataclass
class WindowQuality:
    window_id: str                 # "baseline", "c0".."c5", "t0", "all"
    fps: float
    face_present: float            # share of frames with a face
    luma_ok: float                 # share of frames with face mean luma in [40, 220] (sRGB 0..255)
    neck_coverage: float           # median neck coverage
    motion: float                  # median face-box centre speed, face widths per second
    saturated: float               # share of frames with the face or neck linear mean > 0.95 in any channel
    usable: bool
    reasons: list[str]             # quality.low_fps, quality.no_face, quality.too_dark, quality.too_bright,
                                   # quality.neck_hidden, quality.moving, quality.clipped
@dataclass
class QualityReport:
    windows: dict[str, WindowQuality]
    overall: WindowQuality         # window "all"

def assess(t: np.ndarray, regions: dict[str, RegionSeries], face_box: np.ndarray, frame_w: int,
           events: list[ChallengeEvent], challenge: Challenge | None) -> QualityReport: ...
```

**Provisional rules** (in `thresholds.yaml` under `quality:`):
- `min_fps` 12
- `min_face_present` 0.8
- `luma` [40, 220]
- `min_neck_coverage` 0.5 (the neck only matters for checks that use it)
- `max_motion` 0.5 face widths/s (not for the turn window)

A window is `usable` when every rule that applies passes. Each check decides which rules it needs. For example, `light.face_neck` needs the neck; `turn.follow` ignores motion.

**Tests:**
- one per reason (fps 10 → `quality.low_fps`; luma 30 → `quality.too_dark`; and so on);
- `turn window ignores motion`.

---

## G3. light.response, family C (H5–9; needed for S1)

**Read:** `docs/ARCHITECTURE.md` "Active light challenge", and the old `echo.py` docstring.

**Files:**
- `analysis/echo.py`
- `analysis/checks/light_response.py`
- `server/tests/analysis/test_light_response.py`

**Algorithm:**
- **Echo onset** (port `echo_onset`):
  1. Chromaticity of the skin region's mean linear RGB.
  2. Projection on the direction of the painted colour (`shown_rgb`, linearised, chromaticity minus neutral).
  3. Baseline over the 300 ms before `painted_t_ms`.
  4. Onset = the first 2 consecutive frames above `max(4σ, a_min = 0.003)` within 700 ms.
  5. Hold amplitude check; constant-fraction onset.
- **Per shown colour step:**
  - `answered` = an onset within the delay band [0, 300] ms;
  - `order_ok` = the measured colour direction of the response has a cosine ≥ 0.5 with the expected direction (this catches a replay of a different session's colours).
- **Need ≥ 4 valid steps**, otherwise `abstain` with `light.too_few_steps` plus the window quality reasons.
- **Abstain** when the light is off in the plan (`light.not_run`, so the family state is `not_run`: return `[]` instead), or when `quality.overall.fps < 12`.
- **Risk** = `1 − answered_and_order_ok / valid`. Flag at `light.response.flag_at` (provisional 0.5: fewer than half the steps answered).
- **Features:** `steps_valid`, `steps_answered`, `steps_order_ok`, `median_delay_ms`, `median_snr`.
- **Plot:** `kind "echo"`, series `face` (projection over time), markers at each step's painted time. ≤ 300 points.
- `vote_group "C.response"`, `window_id "all"`.

**Tests** (synthetic, port the old seeds):
- genuine at 30 fps and at 15 fps → usable, not flagged, `steps_answered` ≥ 5 of 6;
- replay (no echo) → flagged with risk ≥ 0.8;
- swapped colour order (render the echoes in the wrong colours) → flagged with order reasons;
- 10 fps → abstain `quality.low_fps`;
- 3 valid steps → abstain;
- delays of 60, 100, 150 and 250 ms are recovered within ±1 frame (port).

---

## G4. sensor.cadence and sensor.duplicates, family B (H6–9)

**Files:**
- `analysis/checks/sensor_stream.py`
- `server/tests/analysis/test_sensor_stream.py`

**Algorithm:**
- **`sensor.cadence`** (port `timing_features`):
  - frame intervals → median fps, coefficient of variation, longest gap, and the share within ±0.5 ms of the median;
  - features as named;
  - **risk** combines two cues:
    - a stall (longest gap > 1000 ms → risk 1, `sensor.stall`);
    - "too perfect" timing (share within ±0.5 ms > 0.98 **and** CV < 0.01 → risk 0.7, `sensor.too_regular`). A hypothesis: a virtual camera may deliver frames on a perfect clock.
  - `flag_at` provisional 0.6.
  - abstain under 30 frames.
- **`sensor.duplicates`:**
  - 64-bit dHash of each frame (port);
  - near-duplicate = Hamming ≤ 2 **and** mean abs difference < 0.5;
  - features `dup_share` and `longest_dup_run`;
  - risk = `min(1, dup_share / 0.05)` (provisional `max_share` 0.05);
  - `flag_at` 1.0.
- Both use `vote_group "B.stream"` (one vote).

**Tests:**
- genuine (jittered 30 fps) → not flagged;
- a 1.2 s gap → cadence flags with `sensor.stall`;
- `virtual_camera` fixture (perfect clock) → cadence risk ≥ 0.7;
- 10% exact repeats → duplicates flags;
- 20 frames → abstain.

---

## G5. light.face_neck and light.background, family C (H9–13)

**Files:**
- `analysis/checks/light_face_neck.py`, `analysis/checks/light_background.py`
- tests for each

**`light.face_neck`** (port, with the old fixes):
- Per colour step, echo onsets and amplitudes for the face (skin) and the neck.
- **A step counts** only when both reach `min_snr` 2× their own threshold, or the neck does while the face is clearly silent. "Clearly silent" needs a face threshold low enough to hear a quarter of the neck's echo; otherwise the step is unclear and counts for neither side.
- **Features:** `pairs`, `median_ratio` (face/neck amplitude), `neck_only_steps`, `median_cf_delta_ms` (informative only, **not** scored: frames are too long).
- **Risk:**
  - risk 1 when `neck_only_steps ≥ 2` (`light.neck_only`: the neck answers our light and the face doesn't, as expected from a pasted face);
  - otherwise risk from `|ln(median_ratio)|` beyond `ln 4` (provisional `ratio_log_tolerance` 1.386, `ratio_log_scale` 0.693).
  - `flag_at` 0.5.
- **Abstain** when the neck coverage is < 0.5 (`quality.neck_hidden`), the neck is saturated, or there are fewer than 3 pairs.
- `vote_group "C.relative"`. The explanation must say this is a hypothesis against live swaps (deck: "measured, not assumed").

**`light.background`:**
- background echo amplitude / face echo amplitude per step (a flat replay screen tends to respond evenly or not at all);
- feature `median_bg_ratio`;
- risk when the ratio is > 0.8 (provisional);
- abstain when the background coverage is low or the face echo is weak;
- `vote_group "C.relative"` (it shares the vote with face_neck).

**Tests:**
- genuine → not flagged;
- `swap_no_face_echo` → flags `light.neck_only`;
- neck half out of frame → abstain;
- a noisy face that is "unclear" is not counted as silent (port the old case);
- background equal to face → background flags.

---

## G6. turn.follow, family D (H10–14)

**Files:**
- `analysis/checks/turn_follow.py`
- `server/tests/analysis/test_turn_follow.py`

**Algorithm:**
- Window: the turn step's `painted_t_ms` to `ended_t_ms + 500`.
- `yaw0` = the median yaw over the 500 ms before `painted`.
- Signed excursion `e(t) = (yaw(t) − yaw0) × (+1 if direction == "left" else −1)`.
- **Features:**
  - `peak_deg` (max `e`);
  - `wrong_peak_deg` (max of `−e`);
  - `latency_ms` (the first time `e` > 10°);
  - `return_deg` (|yaw − yaw0| over the last 300 ms of the window);
  - `face_present`.
- **Outcomes:**
  - `peak_deg ≥ 15` and `return_deg ≤ 10` → usable, risk 0.
  - `wrong_peak_deg ≥ 15` and `peak_deg < 10` → usable, risk 1, `turn.wrong_direction`.
  - No movement (`peak_deg < 10` and `wrong_peak_deg < 10`) with the face present ≥ 0.8 → **abstain** with `turn.not_performed`. A genuine person may simply not have turned; fusion's coverage rule handles it.
  - The face lost during the turn, for more than 40% of the window → usable, risk 0.6, `turn.face_lost`. A hypothesis: swaps can drop the face at large angles.
  - `latency_ms < 150` → reason `turn.too_fast` (feature only, not scored, until data says otherwise).
- `flag_at` 0.5.
- **Plot:** `kind "turn"`, the yaw series and markers at painted/ended.
- `vote_group "D.turn"`.

**Tests:**
- left followed → not flagged;
- right requested but left performed → flags `turn.wrong_direction`;
- no movement → abstain `turn.not_performed`;
- no turn step in the plan → `[]`.

---

## G7. visual.sbi, family D (H12–18)

**Model:** Self-Blended Images (Shiohara & Yamasaki, CVPR 2022), EfficientNet-B4, research-only weights (disclosed in the deck).

**Human step (before H0 or at H12):**
1. Download the FF++ c23 weights from the `mapooon/SelfBlendedImages` README (Google Drive link) to `models/sbi/FFc23.tar`.
2. Do not commit them.
3. Record the source and licence in your status file.

**Files:**
- `analysis/vision/sbi.py`
- `analysis/checks/visual_sbi.py`
- add `torch` (CPU wheel) and `efficientnet_pytorch` to `analysis.txt`
- test: `server/tests/analysis/test_visual_sbi.py`

**Interfaces:**
```python
class SbiModel:
    @classmethod
    def load(cls, path: Path) -> "SbiModel | None": ...   # None if the file is missing or torch is unavailable
    def score(self, crops: list[np.ndarray]) -> np.ndarray: ...   # RGB uint8 380x380 crops -> P(fake) per crop
```
- **Model:** `EfficientNet.from_pretrained("efficientnet-b4", advprop=True, num_classes=2)`, then load the `"model"` state dict from the tar (strip a `net.` prefix if present). Inputs are 0..1 float tensors, as in the SBI repo's inference script. **Check the repo's `inference` code for the exact preprocessing and match it.**
- **Crops:** 8 frames evenly spaced over the session, from frames with a face. Face box expanded by 1.3×, square, resized to 380×380.
- **Risk** = the mean of the top 3 crop scores. Provisional `flag_at` 0.5; the real one comes from G9.
- **Features:** `sbi_mean`, `sbi_top3`, `crops`.
- **Abstain:**
  - the weights are missing → `visual.model_missing`, with the explanation "SBI weights not installed.";
  - fewer than 4 face frames → `quality.no_face`.
- `vote_group "D.detector"`.
- **The explanation** says it is a benchmark-trained detector used as one feature.
- **Runtime:** under 10 s on CPU for 8 crops. The model is loaded once per process (module-level cache).

**Tests:**
- `missing weights abstains` (always runs);
- `scores shape` with a fake model injected (no weights in CI);
- the real-weights test is marked `@pytest.mark.skipif(not weights)`.

---

## G8. sensor.mode_probe, sensor.regions, sensor.prnu, family B (H14–20)

**Files:**
- `analysis/checks/sensor_probe.py`, `analysis/checks/sensor_regions.py`, `analysis/checks/sensor_prnu.py`
- `analysis/vision/noise.py`, `analysis/vision/prnu.py`
- tests for each

**`sensor.mode_probe`** (from `Preflight.probe`):
- features `accepted_unusual` (the 1000×750 request accepted and delivered at that size), `median_switch_ms`, `frames_missing_total`;
- risk 0.7 with `sensor.probe_too_perfect` when the unusual mode was accepted **and** `switch_ms < 150` **and** `frames_missing == 0` (the old measurement: Chromium's fake camera did exactly this, while a real webcam refused);
- risk 1 with `sensor.phantom_switch` when the settings reported a new size but the delivered frames did not change (port the rule);
- abstain when the probe is empty (Safari, Firefox);
- `vote_group "B.probe"`;
- **a hypothesis for OBS and other virtual cameras: measure it at S2.**

**`sensor.regions`** (new):
- temporal noise (frame-difference σ of near-static pixels, in linear light) and sharpness (Laplacian variance), each for face, neck and background, over the baseline and non-step frames;
- features: `noise_face_neck_ratio`, `noise_face_bg_ratio`, `sharp_face_neck_ratio`;
- risk from `|ln ratio|` beyond provisional `ln 2.5`;
- abstain on motion or a hidden neck;
- `vote_group "B.regions"`;
- the explanation says it is a hypothesis: a repainted face may be smoother or noisier than the real neck.

**`sensor.prnu`** (port):
- fingerprint from the odd and even frames, `pce` between the halves, needs ≥ 30 frames with mean luma 60–200;
- feature `pce`;
- **`flag` always false** (supporting only); risk = 1 if PCE < 50, else 0, shown on the console only;
- `vote_group "B.prnu"`.

**Tests:**
- probe: the Chromium-like pattern → risk 0.7; a refused unusual mode → risk 0; an empty probe → abstain;
- regions: equal noise → not flagged; a face 4× smoother than the neck → flagged;
- prnu: a fixed pattern plus noise gives high PCE and no pattern gives low PCE (port); and `flag` is always false.

---

## G9. Calibration on set A (H20–28)

**Files:**
- `scripts/calibrate.py`
- `analysis/thresholds.py` (it reads both files)
- `analysis/thresholds.calibrated.yaml` (generated, committed)
- test: `server/tests/analysis/test_calibrate.py`

**Build:**
- `python scripts/calibrate.py --sessions data/sessions`:
  - re-runs `analyze()` on every labelled **set A** session;
  - for each check's risk on **genuine** sessions only, sets `flag_at` to the genuine 97.5th percentile (at most 1 genuine in 40 flagged per check);
  - with fewer than 20 genuine usable results, keeps the provisional value and says so.
- Writes `thresholds.calibrated.yaml` with `{check_id: {flag_at, n_genuine, source: "calibrated"}}`.
- `Thresholds` prefers calibrated over provisional, and each result's `threshold_source` follows.
- **Never reads set B.** `calibrate.py` exits with an error if it finds a set B session in its input after filtering (a programming error check).
- Paste the per-check n and `flag_at` table into `docs/status/ganeev.md`.

**Tests:**
- the percentile is right on a fake table;
- fewer than 20 → stays provisional;
- set B rows are ignored.

**Then at S3:** apply PLAN §4 (AUC rules). For "measured, not voting" checks, set `voting: false` in `thresholds.yaml`, which makes `flag` always false for them.

---

## G10. turn.identity and pulse.coherence (optional, H24–32; cut-list items 1–2)

**`turn.identity`** (family D, `vote_group "D.identity"`):
- landmark-geometry continuity through the turn: 10 normalised inter-landmark distances (eye corners, nose, mouth, jaw), measured before and after the turn at near-frontal yaw (< 10°);
- risk from the relative change beyond provisional 15%;
- abstain without frontal frames on both sides;
- if time allows, replace it with ArcFace embeddings (insightface `buffalo_l`, research licence, ~280 MB) and record that in your status file.

**`pulse.coherence`** (family A, `vote_group "A.pulse"`, **logged only, `flag` always false**):
- POS rPPG from 5 face regions and the neck;
- only when fps ≥ 20, ≥ 10 s of low-motion frames, and luma is OK; otherwise abstain;
- features `snr_face`, `coherence_face_neck` (0..1);
- **never store or plot the waveform or a heart rate**: `plot` stays `None`;
- the explanation says "experimental, not used in the decision; swaps can carry the driver's real pulse (Seibold 2025)".

**Tests:**
- identity: the same synthetic landmarks → not flagged; scaled-apart landmarks → flagged;
- pulse: 15 fps → abstain;
- a test that asserts no key in `features` contains `hr`, `bpm` or `wave`, and that `plot is None`.

---

## G11. Speed and robustness (H24–36)

- `analyze()` must take under 90 s on 900 frames at 640×480 on the team laptop's CPU. Measure it, write the number in your status file, and parallelise the landmark pass if it is needed.
- **Nuisance tests:** synthetic tube-light flicker (a 100 Hz brightness ripple sampled at 15 fps), glare (a saturated forehead), the neck hidden for half the session, and heavy JPEG (quality 0.5). Expected: abstain or not flagged; **never flagged as an attack because of poor capture**.
- **Run the CLI over every recorded session.** List any check that throws (it must not) or that abstains on more than 50% of genuine sessions; fix what you can, and record the rest.

---

## Sync duties
- **S1:** `analyze()` is live, with G1–G4 merged; the walking skeleton uses real analysis.
- **S2:** every check of G1–G8 is merged. Run the CLI over the recorded sessions, and paste the status counts per check (usable/abstain) in your status file.
- **S3:** calibrated thresholds merged; the voting decisions recorded.
- **Recording (H10–H30):** live-swap sessions on the GPU laptop (see `docs/PLAN.md` section 5).
