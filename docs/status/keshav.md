# Status: Keshav

Only Keshav (and Keshav's agent) edits this file. Newest notes first in each section.

## Tasks
- [x] K1 — scaffold and contract: `contracts.py` verbatim from CONTRACT §3, `contracts.ts` mirror, `bundle.py`, `config.py`, health route, `scripts/dev.py` (8 targets), web scaffold with the 5 final routes and Yash placeholders, typed `api/client.ts`. pytest 5 passed + 2 skipped (7 of 7 with OpenCV installed), vitest 5 passed, lint clean, Brave e2e 1 passed. 2026-10-22.
- [x] K2 — sessions API and storage: rows 2–8 of CONTRACT §2 in `api/sessions.py`, `engine/store.py` (`SessionStore`, re-entrant lock per session), `engine/auth.py` (HMAC customer token, in-memory secret, constant-time compare), `fusion.customer_message`. 17 tests incl. single-use challenge under 8 concurrent requests, 413 limits (31 frames, 201 KB, the 901st frame), expiry 410, path tricks 404, and no risk/flag/check_id/family/outcome in any customer response. 2026-10-23.
- [x] K3 — planner and challenge: `engine/planner.py` (`plan_session` rules 1–5 + face-not-found, `make_challenge`, `rng_for_nonce`), `engine/reason_text.py` (mode.* catalogue). 14 tests: one per rule, first-match order, every emitted code has text (grid of 960 preflights), challenge safety over 200 seeds per mode (no red, no overlap, ≤ 3 colour changes per second, step ids, total_ms), per-nonce randomness. 2026-10-23.
- [x] K4 — analysis runner: `engine/runner.py::run_analysis` (integrity → Ganeev's `analyze()` or the fake → fuse → results.json + decision.json → done; errors, timeouts and bad return values become `analysis.error`, the session never stays "analysing"), `engine/fake_analysis.py` (fake.b/c/d, "FAKE ANALYSIS: not a real measurement."), wired into `/complete`. 7 tests incl. the API end to end. 2026-10-23.
- [x] K5 — ingest integrity: `engine/integrity.py::check_integrity` → `integrity.protocol` (6 rules; protocol_error lists every broken rule) and `integrity.coverage` (frames, batch gaps, span, frames per step window; abstain under 50 frames; flag at ≥ 20% missing batches). `Bundle.frame_rows` (raw frames.jsonl lines, repeats and batch_seq included). 14 tests. 2026-10-23.
- [x] K6 — fusion and outcomes: `engine/fusion.py::fuse` (CONTRACT §8 exactly: usable-only gate, one vote per vote_group, family states, A reported but never votes, first-match outcome rules, provisional), outcome and step-up sentences in `reason_text.py`. 29 tests: the 13-row outcome table, correlated cues one vote, A never votes, family states, reasons order, provisional, customer message mapping. 2026-10-23.
- [x] K7 — agent console v1 + v2: `api/agent.py` (CONTRACT §2 rows 9–12 behind X-Agent-Passcode: session list, `/result` SessionReport, frame JPEGs, `/agent` with 409 before a decision); `web/src/console/**`: passcode gate (sessionStorage), session list (2 s poll), session review (1 s poll until decided): header with PROVISIONAL THRESHOLDS / FAKE ANALYSIS labels and plan reasons, outcome banner ("PulseLens recommends; the agent decides."), challenge timeline (requested vs observed, skipped marked), four family cards with raised / could not judge / checked apart and expandable checks (features, uPlot plot), evidence frames, Approve / Re-verify (creates attempt + link) / Escalate. Tests: 6 API, 1 reason-text mirror, 9 vitest, 6 Brave e2e (passcode, decision with FAKE ANALYSIS, no overflow at 1920 and 1366, action survives reload). 2026-10-23.
- [ ] K8
- [ ] K9
- [ ] K10
- [ ] K11

## Decisions
- **K7: frame images are fetched with the passcode header and shown as blob URLs**, because an `<img src>` cannot send `X-Agent-Passcode`. The evidence frame for a step is chosen from its painted time × the measured fps (the report has no per-frame times); good enough for a thumbnail.
- **K7: `agent.json` also stores `at_ms`** (when the agent acted); `SessionReport.agent_decision` returns only the contract fields.
- **K7: the console's plan-reason sentences** (`web/src/console/reasonText.ts`) mirror the `mode.*` entries of `reason_text.py`; `test_reason_text_mirror.py` fails if they drift.
- **K7: uPlot is loaded only when a plot is drawn** (it reads `matchMedia` on import, which jsdom lacks, and it stays out of the customer pages' bundle).
- **K7: looked at with real data**: the console on the six converted recordings (local `data/converted`) shows the swap at 8 fps as RETRY with B flagged (7.3% repeated frames) and C "could not judge" (< 12 fps); screenshots kept out of git (real faces).
- **K5: `Bundle.frame_rows`** keeps every readable `frames.jsonl` line (repeats, `batch_seq`, `received_at_ms`): `Bundle.frames` drops repeats by design, and integrity needs them for `integrity.duplicate_index` and the batch gaps. Additive field.
- **K5: skipped steps don't count for `integrity.event_order`**: only `shown` events with a painted time are ordered. Total batches = highest `batch_seq` + 1, so a gap at the very end of the upload is not visible (the frame count shows it instead).
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
- **K4 with Ganeev's real `analyze()` (local merge of K4 and `ganeev/G6-turn-follow`, not pushed; 242 tests pass together).** Synthetic sessions → decision: genuine 30 fps and 15 fps PASS; genuine at noise 0.06 PASS (C abstains, B and D carry it); replay RETRY fresh_challenge (C flags), replay attempt 2 RETRY agent_checks; swap without face echo RETRY fresh_challenge (C); virtual camera HUMAN_REVIEW (B + C); another session's colours RETRY (C). **For S2:** a session whose turn was not performed still PASSes on B + C, because `turn.follow` abstains (`turn.not_performed`) instead of flagging.

## Blocked

## Needs a human
