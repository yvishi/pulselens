# Status: Keshav

Only Keshav (and Keshav's agent) edits this file. Newest notes first in each section.

## Tasks
- [x] K1 — scaffold and contract: `contracts.py` verbatim from CONTRACT §3, `contracts.ts` mirror, `bundle.py`, `config.py`, health route, `scripts/dev.py` (8 targets), web scaffold with the 5 final routes and Yash placeholders, typed `api/client.ts`. pytest 5 passed + 2 skipped (7 of 7 with OpenCV installed), vitest 5 passed, lint clean, Brave e2e 1 passed. 2026-10-22.
- [ ] K2
- [ ] K3
- [ ] K4
- [ ] K5
- [ ] K6
- [ ] K7
- [ ] K8
- [ ] K9
- [ ] K10
- [ ] K11

## Decisions
- **K1: e2e runs in the installed Brave, headed; no browser download.** `setup` does not run `npx playwright install chromium` (team decision for this laptop). `web/playwright.config.ts` has a `brave` project (BRAVE_PATH overrides the path) and an opt-in `chromium` project. e2e never reuses running dev servers: they write to `data/sessions`.
- **K1: the JPEG bundle tests skip without OpenCV.** `Bundle.read_frame` needs cv2, which arrives with `server/requirements/analysis.txt` (Ganeev). With it installed all 7 server tests pass.
- **K1: `Bundle.skipped_lines`** (default 0) counts unreadable lines in `frames.jsonl`/`events.jsonl`, which are skipped instead of losing the session. Additive; not a contract model.
- **K1: tests run from the repo root** with `pytest -c server/pyproject.toml --rootdir .` (`pythonpath = ["server"]`), so `testpaths = ["server/tests"]` resolves as the task asks.

## Measurements
- **Real recordings through the real pipeline (2026-10-23).** Six old-prototype sessions (P01, D01 laptop webcam, Brave) converted with `eval/convert_v2.py` (local only, `data/converted`), then K4 runner + K5 integrity + K6 fusion with Ganeev's G1–G6 `analyze()` (local merge, not pushed). 3–12 s per session including face landmarks.

  | Session | Recorded as | fps | Decision | Driven by |
  |---|---|---|---|---|
  | 4e5a24 | genuine | 15.6 | PASS | light.response 6/6 at 93 ms; face_neck usable (face/neck 0.54×); background 2% of the face |
  | b4fec5 | genuine, close-up | 15.6 | PASS | light.response 6/6 at 59 ms; face_neck and background abstain (no neck, no background in frame) |
  | 3c56bd | genuine | 15.6 | RETRY fresh_challenge | **light.response flags a genuine face** (2/6 answered, 1 wrong colour): face and neck both near the noise on 4 flashes, first flash drifting before the pulse |
  | d79105 | live swap | 5.0 | RETRY fresh_challenge | sensor.duplicates 72.4%; light abstains (< 12 fps) |
  | 58484b | live swap | 8.2 | RETRY fresh_challenge | sensor.duplicates 7.3%; light abstains |
  | aedba3 | live swap | 10.3 | RETRY no_flash | low coverage: only B usable, light abstains with quality.low_fps |

  For S2: (1) `3c56bd` is real evidence for Ganeev's `max_silent_threshold` (G3): a weak-echo genuine session should abstain, not flag. (2) No swap reaches HUMAN_REVIEW because only family B flags; mode probe, switch latency, camera name and face-vs-neck sharpness (the V2 findings) are all family B too, so a sub-12-fps swap stays RETRY → agent_checks on attempt 2 unless C or D (head turn) flags.

## Blocked

## Needs a human
