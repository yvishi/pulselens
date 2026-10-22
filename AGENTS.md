# Instructions for coding agents (Claude Code, Codex, Cursor, any other)

PulseLens is an adaptive, camera-first liveness layer for video-KYC (RBI V-CIP). Team Mama Mia builds it in 48 hours for the Amazon AI Cyber Security Hackathon finale (Challenge 03).

## 1. Who you are working for

Three people own three separate parts of this repo:
- **Yash:** capture and the customer screens
- **Keshav:** engine, console and evaluation
- **Ganeev:** analysis

**Before you change anything, know which person you work for.** If the human hasn't told you, ask: "Are you Yash, Keshav or Ganeev?"

Then:
1. Read `docs/PLAN.md` section 2: your owner's paths. **Create and edit files only inside those paths.**
2. Read your task list `docs/tasks/<name>.md` and your status file `docs/status/<name>.md`.
3. Do the next unticked task in order, unless the human names another.

If a task needs a change in a file you don't own, don't make it. Open an issue (`gh issue create --title "[for <Owner>] <what>"`), write it under "Blocked" in your status file, use a local workaround if one exists, and move to the next independent task.

## 2. Read before writing code

1. `docs/ARCHITECTURE.md`: what we build and why.
2. `docs/CONTRACT.md`: shared types, API, bundle format, fusion rules. **Build to it exactly; never change it** (only Keshav does, by the process in `docs/PLAN.md` section 8).
3. `docs/PLAN.md`: ownership, timeline, sync points, git workflow, cut list.
4. `docs/tasks/<name>.md`: your tasks, with files, interfaces and tests.
5. `docs/REFERENCE.md`: what to port from the old repo, and facts already measured.

## 3. How to do a task

1. `git switch main && git pull`, then `git switch -c <name>/<task-id>-<slug>`.
2. Write the tests the task lists first. Run them and see them fail.
3. Implement until they pass.
4. Run `python scripts/dev.py test`, `python scripts/dev.py test-web` and `python scripts/dev.py lint`. All must pass. Run `python scripts/dev.py e2e` when the task touches the browser flow.
5. Tick the task in `docs/status/<name>.md`, with one line on anything surprising (a measured number, a decision, a workaround).
6. Commit with the message `<task-id>: <what>`. Push, then `gh pr create --base main`.
7. Merge it yourself once checks pass: `gh pr merge --merge`. **Never use `--delete-branch` and never delete any branch.**
8. Report to the human: what was done, the test results, and anything blocked.

If something needs a real phone, a person, a GPU, model weights or a decision: stop that part. Write exact steps under "Needs a human" in your status file, and continue with the next independent task.

## 4. Rules that always apply

1. **One clock.**
   - Browser times are `performance.now()` ms, sent as ms since the challenge start `t0`.
   - Never use `Date.now()` in capture or timing maths (ESLint enforces this).
   - Server time is never compared with client time.
2. **Checks never throw.** Bad input → `status: "abstain"` with a quality value and reason codes. Abstaining is never attack evidence.
3. **Poor capture leads to a retry, never a fraud flag.** Low fps, dim light, no visible neck, unsupported camera controls, a budget device and darker skin tone are reasons to abstain or step up, never to flag.
4. **The customer never sees a score**, a family, a check id or an outcome. Only `CustomerStatus.message`.
5. **PulseLens recommends; the agent decides.** No automatic rejection anywhere.
6. **No invented numbers on screen.** Every number comes from a real session, or carries a visible label: `PROVISIONAL THRESHOLDS`, `FAKE ANALYSIS`, `SYNTHETIC` or `ILLUSTRATIVE`.
7. **Thresholds come only from genuine set A sessions.** Never tune on set B. Evaluation on set B runs only after `eval/FROZEN` exists.
8. **Privacy.**
   - Never store, return or plot a heart rate or a pulse waveform.
   - Person codes are pseudonymous (`P01`).
   - No names, real faces, real bank data or secrets in git.
   - `data/`, `models/` and `.env` are gitignored.
   - **This repo is public.**
9. **Attack tooling is out of scope for code.** People record attacks with existing tools (OBS, Deep-Live-Cam, FaceFusion, LivePortrait), only on consenting teammates. Never write code that generates, improves or disguises deepfakes, or that helps evade detection. Detectors, fixtures, labelling and evaluation are in scope.
10. **Tests use synthetic data.** No network, no real faces and no model weights are required in the default test run. Tests that need weights are skipped when the weights are missing.
11. **Mobile first.** Customer screens work at 360 px wide on Android Chrome before desktop polish.

## 5. Commands

All commands run from the repo root on Windows, macOS and Linux; there is no `make`.

| What | Command |
|---|---|
| Setup | `python scripts/dev.py setup` |
| Server (:8000) | `python scripts/dev.py server` |
| Web (:5173) | `python scripts/dev.py web` |
| HTTPS tunnel for phones | `python scripts/dev.py tunnel` |
| Tests | `python scripts/dev.py test` · `python scripts/dev.py test-web` · `python scripts/dev.py e2e` |
| Lint | `python scripts/dev.py lint` |
| Analyse one session | `python -m pulselens.analysis data/sessions/<id> --plots` |

`scripts/dev.py` arrives in task K1 (the first hour). Until it is merged, only K1 is possible.

## 6. Code conventions

- **Python 3.11:** type hints, pydantic v2 models only from `server/pulselens/contracts.py`, ruff (line length 120). Analysis code is pure: NumPy in, dataclasses out. File I/O lives only in `bundle.py`, `engine/store.py`, `api/` and scripts.
- **TypeScript:** strict mode, React 19 + Vite, snake_case for every contract field. `web/src/capture/` is framework-free (no React imports).
- **Small focused files.** One check per file under `server/pulselens/analysis/checks/`.
