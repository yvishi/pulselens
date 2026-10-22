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

## Blocked

## Needs a human
