# Status: Keshav

Only Keshav (and Keshav's agent) edits this file. Newest notes first in each section.

## Tasks
- [x] K1 — scaffold and contract: `contracts.py` verbatim from CONTRACT §3, `contracts.ts` mirror, `bundle.py`, `config.py`, health route, `scripts/dev.py` (8 targets), web scaffold with the 5 final routes and Yash placeholders, typed `api/client.ts`. pytest 5 passed + 2 skipped (7 of 7 with OpenCV installed), vitest 5 passed, lint clean, Brave e2e 1 passed. 2026-10-22.
- [x] K2 — sessions API and storage: rows 2–8 of CONTRACT §2 in `api/sessions.py`, `engine/store.py` (`SessionStore`, re-entrant lock per session), `engine/auth.py` (HMAC customer token, in-memory secret, constant-time compare), `fusion.customer_message`. 17 tests incl. single-use challenge under 8 concurrent requests, 413 limits (31 frames, 201 KB, the 901st frame), expiry 410, path tricks 404, and no risk/flag/check_id/family/outcome in any customer response. 2026-10-23.
- [x] K3 — planner and challenge: `engine/planner.py` (`plan_session` rules 1–5 + face-not-found, `make_challenge`, `rng_for_nonce`), `engine/reason_text.py` (mode.* catalogue). 14 tests: one per rule, first-match order, every emitted code has text (grid of 960 preflights), challenge safety over 200 seeds per mode (no red, no overlap, ≤ 3 colour changes per second, step ids, total_ms), per-nonce randomness. 2026-10-23.
- [ ] K4
- [ ] K5
- [x] K6 — fusion and outcomes: `engine/fusion.py::fuse` (CONTRACT §8 exactly: usable-only gate, one vote per vote_group, family states, A reported but never votes, first-match outcome rules, provisional), outcome and step-up sentences in `reason_text.py`. 29 tests: the 13-row outcome table, correlated cues one vote, A never votes, family states, reasons order, provisional, customer message mapping. 2026-10-23.
- [ ] K7
- [ ] K8
- [ ] K9
- [ ] K10
- [ ] K11

## Decisions
- **K6: `Decision.reasons`** = the outcome sentence, then the step-up suggestion when there is one, then (for an integrity violation) the protocol errors' explanations, then one sentence per flagged family ("Sensor and stream: …", family A marked "reported only, not used in the decision"), then one per abstained family. Every number in them comes from a check's own explanation.
- **K6: "C abstained with a `quality.*` light reason"** reads as: family C's state is `abstained` and at least one C result carries a `quality.*` reason code. `attempt >= 3` wins over every other low-coverage step-up.
- **K2: one re-entrant lock per session for every read and write.** On Windows an atomic replace of `session.json` fails with "Access is denied" while another thread has the file open; the concurrency test hit it until reads took the lock too.
- **K2: `session.json` gets `after_complete_attempts`** (frames or events posted after `/complete`, refused with 409), so K5 can raise `integrity.after_complete`. Additive key.
- **K2: `customer_message` lives in `engine/fusion.py` now** (the K6 interface); `fuse()` joins it in K6. `/complete` hands the session to `app.state.run_analysis` (K4's `engine.runner.run_analysis` once it exists; injectable in tests). Audit events (K8) are not written yet.
- **K3: the 960-preflight grid** in `test_every_reason_has_text` runs `plan_session` over every combination of no-flash, fps, brightness, face size and face found, so a new branch that emits an uncatalogued code fails.
- **K1: e2e runs in the installed Brave, headed; no browser download.** `setup` does not run `npx playwright install chromium` (team decision for this laptop). `web/playwright.config.ts` has a `brave` project (BRAVE_PATH overrides the path) and an opt-in `chromium` project. e2e never reuses running dev servers: they write to `data/sessions`.
- **K1: the JPEG bundle tests skip without OpenCV.** `Bundle.read_frame` needs cv2, which arrives with `server/requirements/analysis.txt` (Ganeev). With it installed all 7 server tests pass.
- **K1: `Bundle.skipped_lines`** (default 0) counts unreadable lines in `frames.jsonl`/`events.jsonl`, which are skipped instead of losing the session. Additive; not a contract model.
- **K1: tests run from the repo root** with `pytest -c server/pyproject.toml --rootdir .` (`pythonpath = ["server"]`), so `testpaths = ["server/tests"]` resolves as the task asks.

## Measurements

## Blocked

## Needs a human
