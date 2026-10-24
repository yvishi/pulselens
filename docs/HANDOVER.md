# Handover: Ganeev's analysis work, 2026-10-25

For the next Claude Code session (cloud). Read this first, then `AGENTS.md`, `docs/CONTRACT.md` §8–9 and
`docs/status/ganeev.md`. You work for Ganeev, who owns the analysis (`server/pulselens/analysis/**`). The user asked
for a demo to judges and for fusion that lets only genuine users pass.

## How the user wants work done
- Answers short and BLUF first. YAGNI and KISS: split work into small tasks, build nothing speculative.
- One branch and one PR per piece of work. Merge with `gh pr merge N -R yvishi/pulselens --merge` (merge commits,
  never squash). **Never delete branches** (AGENTS.md).
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. PR bodies end with
  `🤖 Generated with [Claude Code](https://claude.com/claude-code)`. Never write `@name` mentions.
- Never commit recordings (`data/`), models (`models/`) or `.env`. All are gitignored.
- Cross-owner files (Keshav: `engine/**`, `contracts.py`, `tests/engine/**`, `golden.json`, `docs/CONTRACT.md`;
  Yash: `web/src/capture/**`, `web/src/customer/**`, `web/src/lab/**`) may be edited for this work. The user
  authorised it. List them in the PR body.
- Tests: `python -m pytest -c server/pyproject.toml --rootdir . -p no:cacheprovider server/tests` (about 10 min).
  Lint: `python -m ruff check --config server/pyproject.toml server`. Web, in `web/`: `npm ci`,
  `npx tsc --noEmit -p .`, `npm run lint`, `npm run test`. Setup: `python scripts/dev.py setup`.
- After an intended analysis change, regenerate the golden **once**, at the end:
  `PULSE_UPDATE_GOLDEN=1 pytest ... server/tests/engine/test_golden.py`. Review its diff: decisions should not
  change unless intended. The golden is pinned with no SBI model (and ArcFace, once G10c lands) via monkeypatch in
  `test_golden.py`.

## Where main is (a80fff4)
All merged: G1–G11, T12–T21, G9 `scripts/calibrate.py`, G10 `turn.identity` (geometry) and `pulse.coherence`
(logged only), `python -m pulselens.analysis <data_dir> --all` (batch report), S2 real-session fixes (#96), and
**#105, the replay hole**. #105 changed:
- `turn.follow`: ≥ 15° the wrong way without reaching 15° the asked way is now `turn.wrong_direction` (risk 1).
- `CheckResult.voting` (default true). Measured-only results (SBI, PRNU, pulse, `sensor.regions`) cover no family.
- Fusion (CONTRACT §8): a turn shown but not performed gives `RETRY_STEP_UP` / `fusion.challenge_not_done`.
  **PASS needs the live challenge verified**: `turn.follow` usable and unflagged, or `light.response` when the plan
  has no turn (`fusion.liveness_not_shown` otherwise).
- `fake_analysis` D result id is `turn.follow`.

Not voting yet, until calibrated on ≥ 20 genuine sessions: `visual.sbi`, `sensor.regions`. The `sensor.mode_probe`
phantom switch is noted, not scored. The `light.face_neck` ratio tolerance is ln 8.

## Real-data facts (the recordings are only on Ganeev's laptop, so you cannot rerun them)
16 genuine set A sessions: P01, Acer laptop webcam 640×480, 31 fps (15.8 fps in dim light).
- **Every check is clean on genuine sessions after the fixes:** 0 false flags in 16.
- `turn.identity` geometry change: 1.5–4.8%.
- **Head micro-motion before the prompt** (yaw, 5th to 95th percentile): genuine 0.55–37°. A still image through
  OBS Virtual Camera: **0.05°**.
- **Attack sessions recorded by the user:**
  - YouTube video replayed to the webcam: the turn went 24° the wrong way, 12.5° the asked way. It used to PASS;
    now it is RETRY (`turn.wrong_direction`). The screen filled the frame, so `light.background` abstained (6%
    background). The glossy screen made `light.response` "answer" at 25 ms.
  - OBS Virtual Camera with a still image: HUMAN_REVIEW. Flags: `sensor.too_regular`, `sensor.duplicates` (100%),
    `light.no_echo`. `turn.follow` only abstained (head moved 0.002°), which is what `ganeev/frozen-head` fixes.
    `pulse.coherence` gave a meaningless 1.0 on identical frames.
- `visual.sbi` scores real faces 0.51–0.99 (a gap between FF++ and a webcam, not a bug), and 0.999 on the replay.
- `pulse.coherence`: face SNR 2.2–7.1 dB, face–neck coherence 0.15–0.42 (the neck box is mostly shirt). Logged only.

## Open branches, in merge order (all pushed; no PRs yet)
Each branch was cut from 81f1290 or a80fff4. **Rebase each onto `origin/main` before its PR**: main moved with #105.
Expect conflicts in the append-only shared files `specs.py`, `analysis/__init__.py` (CHECKS), `thresholds.yaml`,
`analysis/reason_text.py`, `tests/fixtures/synth.py` and `docs/status/ganeev.md`. Keep both sides.

### 1. `ganeev/frozen-head` (WIP, mine; small)
- Done: `turn.follow` flags `turn.frozen` (risk 1) when the yaw spread before the prompt is under `frozen_deg`
  0.2 over ≥ `frozen_min_frames` 30 frames. `pulse.coherence` abstains on identical frames.
- **To do:**
  - Tests: synthetic frozen yaw gives `turn.frozen`. synth has no "frozen" option yet; the virtual-camera kind has
    zero noise on yaw? Check `_yaw`. Otherwise add a `head_jitter` option. Pulse identical frames → abstain.
  - Then the full suite and golden: the `virtual` case may change, to `turn.frozen` flagging in D. Expected.
  - PR, merge.

### 2. `ganeev/G10c-arcface-identity` (WIP: the agent stopped at the usage limit)
- Done: `vision/arcface.py` (InsightFace `w600k_r50.onnx`, ArcFace R50, 5-point alignment from MediaPipe
  landmarks, onnxruntime CPU), `turn_identity.py` uses the ArcFace cosine when the model exists and falls back to
  geometry; tests; golden pin; `onnxruntime` in requirements.
- **To do:**
  1. Read the diff. Make sure the tests pass.
  2. **Add the rule:** `turn.identity` abstains with `turn.not_performed` when the largest |yaw − yaw0| in the turn
     window is below `turn.follow`'s `min_peak_deg`. A still image never turns, yet `turn.identity` reported
     "same face" and made D look covered. Add a test.
  3. The model is gitignored and research-only, so it can't be downloaded in CI: the real-model test must skip.
     The `min_similarity` threshold must keep genuine sessions far from flagging; real-session similarity was never
     measured. If unsure, make the ArcFace score reported-only and say so.
  4. Full suite, PR, merge.

### 3. `ganeev/G12-edge-flicker` (committed by the agent; not verified by me)
- `visual.edge_flicker` (D.edge): the face-edge ring vs the inner face, frame-to-frame change on still frames.
  **Measured, not voting.** Synth `edge_flicker` option; tests; real numbers in its status-doc note.
- **To do:** rebase, review, full suite, PR, merge.

### 4. `ganeev/challenge-nod-digits` (committed, 4 commits; the agent stopped before verifying)
- New live prompts after the turn, behind `challenge.extra_prompts` in `config.yaml`:
  - **nod**: `turn.nod`, D.nod, pitch ≥ 10°;
  - **3 random spoken digits**: `visual.lip_digits`, D.lips. The mouth must open within 150–1200 ms of each digit
    (2 of 3) and be quieter in the gaps. No audio, and digit identity is not recognised.
- Contracts: new step types. Planner, web capture UI (`livePrompts.ts`, `LivePrompts.tsx`, EN/HI strings), console
  timeline, `context.py` (`pitch`, `mouth_open`), quality windows.
- Fusion row 4 is generalised: any shown live prompt not performed → `fusion.challenge_not_done`. PASS still
  requires only `turn.follow`.
- **To do:**
  1. Rebase (fusion.py and test_fusion.py conflict with #105: keep the `voting` coverage and the liveness rule, and
     extend `_turn_skipped` to the new codes).
  2. Full Python suite, web typecheck, lint and tests. Run the Playwright e2e if possible.
  3. PR, merge.
  4. **Demo risk:** the capture flow changed. If anything is shaky, set `challenge.extra_prompts: false` (one line)
     before the demo.

### 5. After all four
- Regenerate the golden once and review it. Update `docs/status/ganeev.md` (Decisions: frozen head, ArcFace, edge
  flicker, nod and digits, fusion rows). Delete this file's "Open branches" section or mark it done.
- Ask the user to pull on the laptop and restart the servers (below), then do one live genuine run, one YouTube
  replay and one OBS still image. Expected: PASS, RETRY (or HUMAN_REVIEW), HUMAN_REVIEW.

## Fusion policy: what the user asked, and the honest answer
The user wants only genuine users to pass and every kind of deepfake caught. The policy is now liveness-first:
- a session must prove liveness (a verified random turn);
- every not-performed prompt is a fresh challenge;
- two independent families flagging → human review.

Do not promise "all deepfakes caught". A live face swap driven by a real attacker follows prompts and moves its lips;
`light.face_neck` (neck-only echo), `turn.identity` (ArcFace) and the edge flicker are the checks aimed at it. None
has seen a real `live_swap` recording yet: **recording ~10 live-swap sessions (Deep-Live-Cam into the OBS Virtual
Camera, consenting teammates only) is the most valuable next step**, followed by 20+ genuine sessions to run
`scripts/calibrate.py`.

Possible further fusion change, discussed but **not decided**: whether a D flag from the turn itself
(`turn.wrong_direction`, `turn.frozen`) should go straight to HUMAN_REVIEW instead of RETRY. Today one family →
RETRY with a fresh challenge, and attempt 2 → agent checks. Ask the user before changing it.

## Running the demo on the laptop (user's machine, Windows)
- `git pull`, then the API: `.venv\Scripts\python -m uvicorn pulselens.api.main:app --app-dir server --port 8000`.
  Web: `cd web && npm run dev` (http://localhost:5173). Console `/console`, customer link from there, `/lab` for
  labelled recordings.
- Models must exist locally:
  - `python scripts/fetch_models.py` and `python scripts/fetch_web_models.py`. **The browser model missing makes
    every session CONSTRAINED.**
  - SBI weights at `models/sbi/FFc23.tar`: Google Drive id `1X0-NYT8KPursLZZdxduRQju6E52hauV0`, research only.
  - ArcFace at `models/arcface/w600k_r50.onnx`, from InsightFace `buffalo_l.zip` v0.7, research only.
- Console passcode is `AGENT_PASSCODE` from `.env`, default `change-me`.
- Real sessions for checks: `python -m pulselens.analysis data/sessions --all`. Calibration:
  `python scripts/calibrate.py --sessions data/sessions` (needs ≥ 20 genuine per check).
