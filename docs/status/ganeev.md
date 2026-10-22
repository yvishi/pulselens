# Status: Ganeev

Only Ganeev (and Ganeev's agent) edits this file. Newest notes first in each section.

## Tasks
- [x] G1 — package skeleton, vision base, `analyze()`, synthetic bundles, CLI. Vision base ported from PulseLensV2 (byte-identical to PulseLensFinal for these files); `synth.py` rewritten for the new bundle (Challenge + ChallengeEvent, `write_bundle`, 478-point `landmarks.jsonl`). 30 analysis tests; full suite 37 passed, 0 skipped (Keshav's 2 OpenCV bundle tests now run), lint clean. `CHECKS` is still empty: real analysis returns no results until G3/G4. 2026-10-23.
- [ ] G2
- [ ] G3
- [ ] G4
- [ ] G5
- [ ] G6
- [ ] G7
- [ ] G8
- [ ] G9
- [ ] G10
- [ ] G11

## Decisions
- **G1: `guarded(*specs)` takes the `CheckSpec`s a check emits** (`@guarded(specs.SENSOR_CADENCE, specs.SENSOR_DUPLICATES)`), not a bare `guarded(fn)`: without them it cannot name the abstain. One abstain per spec, `quality.check_error`, traceback logged. `analyze()` also skips (and logs) a check that raises without the guard.
- **G1: no readable frames → one abstain per CONTRACT §9 check** with `quality.no_frames` (empty dir, missing dir, all JPEGs corrupt). With frames, each check decides for itself.
- **G1: the landmarks cache is not written when `face_landmarker.task` is missing**, so a later run with the model can still find faces.
- **G1: synthetic frames are 320x240, not 160x120,** so the old geometry tests (face 80x110, chin at 150) port unchanged. In every kind the wall answers 5% of the screen light; `replay` and `virtual_camera` have no face or neck echo; `virtual_camera` also has a perfect clock and zero noise. Default echo SNR is about 77 (noise 0.003), so G3 should also test at higher noise.
- **G1: `result(..., voting=False)` keeps `flag` false**, for `voting: false` checks in `thresholds.yaml` (prnu, pulse; S3 decisions).

## Measurements
- **G1:** `build_context` 3.4 ms per frame at 320x240 with cached landmarks (404 frames in 1.38 s) on Keshav's laptop. The landmark pass at 640x480 is not measured yet (G11).

## Blocked

## Needs a human
- **Yaw sign (G1, with Yash's Y2).** `analysis/vision/pose.py` computes `yaw = atan2(M[0,2], M[2,2])`, the same angle as the browser's `atan2(m[8], m[10])`, but nobody has checked the sign on a real face yet. Steps: record a lab session, turn your head to **your own left** during the turn, run `python -m pulselens.analysis data/sessions/<id>`, open `<id>/landmarks.jsonl`, and confirm `yaw` goes positive. If it goes negative, flip the sign in `pose.py` and tell Yash.
- **SBI weights (G7).** Download `FFc23.tar` from the Google Drive link in the `mapooon/SelfBlendedImages` README to `models/sbi/FFc23.tar`. Do not commit it; record the source and licence here.
