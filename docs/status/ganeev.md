# Status: Ganeev

Only Ganeev (and Ganeev's agent) edits this file. Newest notes first in each section.

## Tasks
- [x] G1 — package skeleton, vision base, `analyze()`, synthetic bundles, CLI. Vision base ported from PulseLensV2 (byte-identical to PulseLensFinal for these files); `synth.py` rewritten for the new bundle (Challenge + ChallengeEvent, `write_bundle`, 478-point `landmarks.jsonl`). 30 analysis tests; full suite 37 passed, 0 skipped (Keshav's 2 OpenCV bundle tests now run), lint clean. `CHECKS` is still empty: real analysis returns no results until G3/G4. 2026-10-23.
- [x] G2 — quality gate (`analysis/quality.py`: `WindowQuality`, `QualityReport`, `assess`), filled into `ctx.quality` by `build_context`; `light.response` now leaves out steps whose window is not usable and adds the window reasons to its abstain. 16 quality tests; full suite 127 passed, lint clean. Stacked on G3 (PR #7). 2026-10-23.
- [x] G3 — `light.response` (`analysis/checks/light_response.py`, C.response) with `analysis/echo.py` ported from V2 (onset, constant-fraction onset, SNR gate; input is now a step's painted/ended/colour). 44 ported echo tests + 21 light tests; full suite 111 passed, lint clean. Stacked on G4 (PR #6). 2026-10-23.
- [x] G4 — `sensor.cadence` and `sensor.duplicates` (`analysis/checks/sensor_stream.py`, vote group `B.stream`), ported from V2's `camera_timing`/`camera_duplicates`, now in `CHECKS`. 10 tests; full suite 46 passed, lint clean. Stacked on G1 (PR #4). 2026-10-23.
- [ ] G5
- [ ] G6
- [ ] G7
- [ ] G8
- [ ] G9
- [ ] G10
- [ ] G11

## Decisions
- **G2: `WindowQuality.usable` ignores the neck; `blocking(neck=True)` adds it.** The neck rule only matters for checks that use the neck (face_neck, sensor.regions), as the task says. `quality.neck_hidden` is always in `reasons`.
- **G2: the motion rule does not apply in a turn window, and the turn's frames are left out of "all"'s motion,** so asking the person to turn never makes the whole session "moving".
- **G2: luma is the sRGB luma (0..255) of the skin region's mean linear colour; `luma_ok` is over face frames only** (no face is `quality.no_face`, not dark). too_dark vs too_bright comes from the median luma. Two new provisional keys: `min_luma_ok` 0.8 and `max_saturated` 0.2.
- **G2: `assess(..., thresholds=)` takes the thresholds as a keyword** (the task's signature has no way to reach `quality:` otherwise); without it the file is loaded. `frame_w` is accepted but unused: motion is in face widths.
- **G2 → light.response: a step whose window is not usable is left out** (it counts as neither answered nor silent). Its reasons join the abstain when fewer than 4 steps remain, e.g. "6 had poor capture (the face was too dark to measure)". The fps and no-face abstains now come from the "all" window.
- **Test speed:** the server suite takes about 60 s now, because every light test renders its own synthetic session. Share the sessions with module-scoped fixtures at G11 if it gets in the way.
- **G3: "unclear vs silent" applies to light.response too, not only face_neck.** A step with no echo counts as silent only when its 4-sigma threshold is at most half the session's median answered echo, and at most `max_silent_threshold` (0.012, provisional). Otherwise it is unclear and left out. Without this, a synthetic genuine session at noise 0.06 was **flagged** (3 of 6 answered). Now it abstains with `light.too_few_steps` + `light.weak_face_echo`. **Trade-off:** a replay at synthetic noise 0.02 also abstains instead of flagging. `max_silent_threshold` is the number to set from real bright-room webcam sessions at S2 (REFERENCE: bright-room echo SNR ~5).
- **G3: `order_ok` is measured separately from the onset** (`echo.response`: mean chromaticity change over [painted + 200, ended + 100] ms, cosine with the shown colour ≥ 0.5) and only for steps that responded. A step that changes colour the wrong way is `light.wrong_order`, not `light.no_echo`. The synthetic `swap_colours=True` (each step echoes the colour half a sequence away) flags with `light.wrong_order`.
- **G3: `median_snr` is in threshold units** (hold amplitude / max(4 sigma, a_min)), so 1 is just detectable.
- **G3: fps below 12 and face present < 80% abstain before any step is measured** (`quality.low_fps`, `quality.no_face`). G2's window quality reasons are added once G2 exists.
- **G3: an echo outside the 0–300 ms band counts as a failed step** (the face did change, just not on time).
- **G4: dHash distance and frame difference are measured in `build_context`** (`hamming_prev`, `mad_prev`, against the previous *readable* frame), so frames are decoded once. A corrupt frame is never counted as a duplicate.
- **G4: `sensor.too_regular` flags (risk 0.7 vs flag_at 0.6), as the task says, but it is a hypothesis.** The old repo only measured evenness because hardware-timestamped webcams are very even too. At S2, check `exact_share` and `cv` on real webcams and phones before trusting it.
- **G4: duplicates may need a guard for phones with heavy temporal denoising.** A noise-free still source gives near-identical frames (the synthetic virtual camera: 96% repeats). Check the duplicate share of genuine phone sessions in a still, dim room at S2/G11.
- **G4: too few frames for a stream check abstain with `quality.low_fps`** (fewer than 30 frames, or 30 compared pairs).
- **G1: `guarded(*specs)` takes the `CheckSpec`s a check emits** (`@guarded(specs.SENSOR_CADENCE, specs.SENSOR_DUPLICATES)`), not a bare `guarded(fn)`: without them it cannot name the abstain. One abstain per spec, `quality.check_error`, traceback logged. `analyze()` also skips (and logs) a check that raises without the guard.
- **G1: no readable frames → one abstain per CONTRACT §9 check** with `quality.no_frames` (empty dir, missing dir, all JPEGs corrupt). With frames, each check decides for itself.
- **G1: the landmarks cache is not written when `face_landmarker.task` is missing**, so a later run with the model can still find faces.
- **G1: synthetic frames are 320x240, not 160x120,** so the old geometry tests (face 80x110, chin at 150) port unchanged. In every kind the wall answers 5% of the screen light; `replay` and `virtual_camera` have no face or neck echo; `virtual_camera` also has a perfect clock and zero noise. Default echo SNR is about 77 (noise 0.003), so G3 should also test at higher noise.
- **G1: `result(..., voting=False)` keeps `flag` false**, for `voting: false` checks in `thresholds.yaml` (prnu, pulse; S3 decisions).

## Measurements
- **G3 (synthetic, 6 steps):** genuine median delay 88 ms at 30 fps and 81 ms at 15 fps (true 100 ms after painted; the onset is the 4-sigma crossing), SNR 18–22 at noise 0.003. The 60/100/150/250 ms delays are recovered within one frame. A whole `analyze()` on a 403-frame session takes 1.3 s.
- **G1:** `build_context` 3.4 ms per frame at 320x240 with cached landmarks (404 frames in 1.38 s) on Keshav's laptop. The landmark pass at 640x480 is not measured yet (G11).

## Blocked
- **#5 [for Keshav] `Bundle.read_frame` raises on a 0-byte JPEG.** Workaround in place: `analysis/context.py::read_frame` returns None instead. Remove it once #5 is fixed.

## Needs a human
- **Yaw sign (G1, with Yash's Y2).** `analysis/vision/pose.py` computes `yaw = atan2(M[0,2], M[2,2])`, the same angle as the browser's `atan2(m[8], m[10])`, but nobody has checked the sign on a real face yet. Steps: record a lab session, turn your head to **your own left** during the turn, run `python -m pulselens.analysis data/sessions/<id>`, open `<id>/landmarks.jsonl`, and confirm `yaw` goes positive. If it goes negative, flip the sign in `pose.py` and tell Yash.
- **SBI weights (G7).** Download `FFc23.tar` from the Google Drive link in the `mapooon/SelfBlendedImages` README to `models/sbi/FFc23.tar`. Do not commit it; record the source and licence here.
