# PulseLens: 48-hour build plan (team Mama Mia)

**Goal:** in 48 hours, rebuild PulseLens from scratch to the final deck's architecture (`docs/ARCHITECTURE.md`). Ship a working prototype that runs the deck's four live demo scenarios on an agent console, with honest measured results.

**Team and agents:** three people. Each drives their own coding agent (Claude Code, Codex, Cursor or another); all agents read `AGENTS.md` first.

| Person | Owns (architecture column) | Task list |
|---|---|---|
| **Yash** | **Applicant device**: capture SDK, quality preflight, challenge rendering, customer screens, Lab recording screen, browser e2e | `docs/tasks/yash.md` (Y1 to Y10) |
| **Keshav** | **Engine and bank side**: repo scaffold, contract, API, session orchestrator and planner, ingest and integrity, fusion and outcomes, agent console, evidence record, evaluation | `docs/tasks/keshav.md` (K1 to K11) |
| **Ganeev** | **Analysis**: vision base, quality gate, the checks of families A to D, the SBI model, thresholds and calibration | `docs/tasks/ganeev.md` (G1 to G11) |

**Stack:**
- **Server:** Python 3.11, FastAPI, pydantic v2, NumPy, OpenCV, MediaPipe, PyTorch on CPU for SBI.
- **Web:** one React 19 + Vite + TypeScript app with routes `/customer/:id`, `/lab`, `/console`, `/console/:id`. uPlot for charts. Vitest and Playwright for tests.
- **Storage:** files on disk under `data/`. No database.

**How priorities work:** the deck's demo first (section 6), the measured results table second, the polish of the Lab screens last. When behind, cut from section 7.

---

## 1. Read order for every agent

1. `AGENTS.md`: the rules.
2. `docs/ARCHITECTURE.md`: what we are building, and why.
3. `docs/CONTRACT.md`: the shared interfaces. Build to it exactly.
4. This file, especially sections 2 and 3.
5. Your own task list in `docs/tasks/<name>.md`, and your status file `docs/status/<name>.md`.
6. `docs/REFERENCE.md`: what to port from the old repo, and the facts already measured.

---

## 2. File ownership (the anti-collision rule)

**You only create or edit files under your own paths.** If you need a change in someone else's file, open a GitHub issue titled `[for <Owner>] <what>` (`gh issue create`) and carry on with a local workaround. Never edit their file "just a little".

| Path | Owner |
|---|---|
| `AGENTS.md`, `CLAUDE.md`, `README.md`, `docs/PLAN.md`, `docs/CONTRACT.md`, `docs/ARCHITECTURE.md`, `docs/REFERENCE.md`, `docs/tasks/*` | **Keshav** (edits only at sync points, after all three agree) |
| `.gitignore`, `.env.example`, `config.yaml`, `scripts/dev.py` | Keshav |
| `server/pyproject.toml`, `server/requirements/engine.txt` | Keshav |
| `server/pulselens/__init__.py`, `contracts.py`, `bundle.py`, `config.py` | Keshav |
| `server/pulselens/api/**`, `server/pulselens/engine/**` | Keshav |
| `server/tests/conftest.py`, `server/tests/engine/**` | Keshav |
| `eval/**`, `scripts/verify_audit.py`, `scripts/purge.py` | Keshav |
| `web/package.json`, `web/package-lock.json`, `web/vite.config.ts`, `web/tsconfig*.json`, `web/index.html`, `web/playwright.config.ts`, `web/eslint.config.js` | Keshav |
| `web/src/main.tsx`, `web/src/App.tsx`, `web/src/contracts.ts`, `web/src/api/**`, `web/src/shared/**`, `web/src/console/**` | Keshav |
| `web/e2e/console.spec.ts` | Keshav |
| `server/requirements/analysis.txt` | **Ganeev** |
| `server/pulselens/analysis/**` | Ganeev |
| `server/tests/analysis/**`, `server/tests/fixtures/**` | Ganeev |
| `scripts/fetch_models.py`, `scripts/calibrate.py` | Ganeev |
| `web/src/capture/**`, `web/src/customer/**`, `web/src/lab/**` | **Yash** |
| `web/e2e/customer.spec.ts`, `web/e2e/lab.spec.ts`, `web/e2e/support/**`, `web/e2e/fixtures/**` | Yash |
| `scripts/fetch_web_models.py`, `web/public/models/` (gitignored contents) | Yash |
| `docs/status/yash.md` · `docs/status/keshav.md` · `docs/status/ganeev.md` | each person their own |

**Placeholders.** At K1, Keshav creates `web/src/customer/CustomerPage.tsx` and `web/src/lab/LabPage.tsx` as one-line placeholder components, so `App.tsx` never has to change again. From the moment K1 is merged, those files belong to Yash.

**Dependencies:**
- **Web:** `web/package.json` is Keshav's. K1 installs every web dependency listed in `docs/tasks/keshav.md` K1, including Yash's (`@mediapipe/tasks-vision`, `qrcode`, `uplot`). If Yash needs another package, Yash opens an issue; Keshav adds it the same hour.
- **Python:** each side has its own requirements file. Install both: `uv pip install -r server/requirements/engine.txt -r server/requirements/analysis.txt`.

---

## 3. Timeline and sync points

`H` = hours since the start of the finale. All three phases run in parallel. A sync point is a 20-minute call: everyone merges to `main`, runs the sync check, and the plan is adjusted.

| Hours | Yash | Keshav | Ganeev |
|---|---|---|---|
| **H0–1** | device prep (Y0), read the old capture code | **K1 scaffold + contract** (the only blocking task) | synthetic bundle generator design, read the old vision code |
| **S0 at H1** | **K1 merged.** Everyone pulls `main` and runs `python scripts/dev.py setup`. | | |
| H1–8 | Y1 camera + clock + grabber, Y2 preflight + probe, Y3 challenge renderer, Y4 uploader + customer flow v1 | K2 sessions API, K3 planner + challenge, K4 ingest, K5 integrity, K6 fusion, K7 console v1 | G1 vision base + analyze() skeleton + fixtures, G2 quality gate, G3 light.response, G4 sensor.cadence/duplicates |
| **S1 at H8** | **Walking skeleton:** a genuine laptop session goes customer → server → analysis → fusion → console and shows an outcome. Real camera, real light echo, no turn yet. | | |
| H8–18 | Y5 head-turn prompt, Y6 coaching + no-flash + EN/HI, Y7 phones (Android, iPhone) + HTTPS tunnel, Y8 Lab recording page | K7 console v2 (evidence by family, timeline, plots, agent actions), K8 evidence record, K9 pairing + QR + tunnel | G5 light.face_neck/background, G6 turn.follow, G7 visual.sbi, G8 sensor.mode_probe/regions/prnu |
| **H10 onwards** | **Recording starts (human):** Yash genuine sessions; Keshav OBS and replay sessions; Ganeev live swaps on the GPU laptop (section 5). | | |
| **S2 at H18** | **Every core check in.** All four scenarios run end to end (outcome may still be wrong). First genuine-vs-attack numbers from `eval/separation.py`. | | |
| H18–30 | Y9 capture hardening (fps drop downgrade, exposure lock, budget Android, dim room), Y10 e2e suite | K10 eval (APCER/BPCER, groups, Wilson CI), K11 hardening (timeouts, purge, demo reset) | G9 calibrate on set A, G10 turn.identity + pulse.coherence (optional), G11 analysis speed + robustness |
| **S3 at H30** | **Calibrated and evaluated.** Thresholds from set A genuine sessions; set B results printed. Decide which checks vote (section 4). | | |
| H30–40 | demo polish on phones, rehearse scenarios 1–2 | console polish, results slide numbers, rehearse 3 | fix analysis misses found in rehearsal, rehearse 4 |
| **H40** | **Code freeze.** After this, only demo-blocking fixes, each as its own PR. | | |
| H40–48 | rehearsals (5 runs per scenario), fallback screen recording by H44, deck numbers updated from `eval/out` | | |

**Sync checks** (run by whoever merges last before the sync):
- **S1:** `python scripts/dev.py test` and `python scripts/dev.py test-web` both pass on `main`. One manual laptop session reaches a `decision.json` and the console shows it.
- **S2:**
  - The S1 checks pass.
  - `python scripts/dev.py e2e` passes.
  - One recorded session of each kind (genuine, replay_screen, virtual_camera, live_swap) has a `results.json` with all of families B, C and D present.
- **S3:**
  - The S2 checks pass.
  - `eval/out/report.md` exists.
  - `eval/FROZEN` exists.

---

## 4. Decision rules at S3 (which checks vote)

For each check, with set A only: genuine vs each attack kind, AUC from `eval/separation.py`.

| AUC | Decision |
|---|---|
| ≥ 0.80 | votes |
| 0.65 to 0.80 | votes, but the console shows it as "weak evidence" |
| < 0.65 | **measured, not voting**: Ganeev sets `flag` to always false for it, and it still shows on the console |

Record each decision in `docs/status/ganeev.md` under "Decisions". The deck shows only numbers from `eval/out`, labelled with n.

---

## 5. Human tasks (no agent can do these)

| When | Who | What |
|---|---|---|
| Before H0 | all | Install Python 3.11, Node 22.12+, `uv`, `gh` (logged in), `git`. Clone the repo and the old repo for reference (see `docs/REFERENCE.md`). |
| Before H0 | Yash | `cloudflared` installed and tested from a phone on mobile data (phones need HTTPS for the camera and motion sensors). |
| Before H0 | Ganeev | GPU laptop: Deep-Live-Cam (and FaceFusion if time) installed and tested once on a consenting teammate; OBS Studio with its virtual camera. SBI weights downloaded (see G7). |
| Before H0 | Keshav | 20 printed consent forms; a paper code sheet mapping people to `P01…` (never in git). |
| H10–H30 | Yash | Genuine recordings on `/lab`: each available device (Android, iPhone, laptop webcam, USB webcam), bright and dim light, 2 repeats, teammates and consenting volunteers. Target ≥ 60 genuine sessions. |
| H10–H30 | Keshav | Attack recordings on `/lab`: `replay_screen` (phone playing a teammate's earlier video in front of the webcam) ×10; `virtual_camera` (OBS virtual camera playing a pre-recorded teammate clip) ×10. |
| H10–H30 | Ganeev | Attack recordings on `/lab`: `live_swap` (Deep-Live-Cam into the OBS virtual camera, swapping consenting teammates' faces only) ×10; `photo_animation` (LivePortrait, set B only) ×6 if time. |
| H40–44 | all | Rehearse; record a fallback screen video of all four scenarios. |

**Sets:** decide A or B per **person** at enrolment, about 60/40, so no person is in both. LivePortrait goes to set B only (the held-out tool). Write the person→set map only on the paper sheet; `Label.set` carries it.

**Ethics (always):**
- Attack tools are run by a human, only on consenting teammates.
- Red-team work with attack tooling follows `AGENTS.md` rule 9: only against our own PulseLens running offline on a local system; attack code and its outputs never go into this public repo.
- No real public figures.
- No real bank data.

---

## 6. The demo (about 6 minutes, the deck's four scenarios)

Setup: the console (`/console`) on the projector, the customer on a phone or a laptop. Before each run, the presenter reads the "what we expect" line; after it, points at what was measured. If they differ, say why.

| # | Customer | Expected (hypothesis) | What the console must show |
|---|---|---|---|
| 1 | genuine user, phone browser, good light | CAPABLE; B, C and D not raised; **PASS** | plan + reasons, the colour timeline with the face answering each step, turn followed, PASS |
| 2 | genuine user, cheap USB webcam, dim room | coached; fps < 12 or weak echo, so light abstains; CONSTRAINED or NO_FLASH; **PASS** (B + D usable) or **RETRY / STEP-UP** | "abstained, not failed" on C with the reason; the step-up choice |
| 3 | pre-recorded teammate clip through the OBS virtual camera | C flags (no answer to today's colours); B may flag; **HUMAN REVIEW** if B also flags, else **RETRY / STEP-UP** | the requested vs observed timeline; the integrity panel |
| 4 | live face swap (Deep-Live-Cam) on a consenting teammate | **shown as measured, including any miss** | whatever happened, with the honest label |

---

## 7. Cut list (cut from the top when behind)

1. `pulse.coherence` (family A)
2. `turn.identity`
3. `sensor.prnu`
4. `light.background`
5. Hindi strings
6. Exposure lock (Y9 part)
7. Evidence-record hash chain (keep plain logging)
8. Lab recording screen polish (keep the bare form)

**Never cut:**
- `light.response` and `light.face_neck`
- `turn.follow`
- `sensor.cadence` and `sensor.duplicates`
- `integrity.*`
- the planner with three modes
- fusion with the three outcomes
- the console with failed vs abstained
- the customer flow on Android Chrome and a laptop
- `eval` with "x of n" numbers

---

## 8. Git workflow

- **Branches:**
  - Work on `<name>/<task-id>-<slug>`, for example `yash/Y3-challenge-renderer`.
  - One task per branch.
  - **Never delete branches, even after merging.**
- **Commits:**
  - Small, each with passing tests.
  - Message: `<task-id>: <what>`, for example `G3: light.response echo onset and order`.
- **Merging:**
  - Push, then open a PR to `main` with `gh pr create`.
  - Merge it yourself once your checks pass (`gh pr merge --merge`, with **no** `--delete-branch`).
  - Because the paths never overlap, merges are not reviewed by others, except PRs touching `docs/CONTRACT.md` (see below).
- **Staying current:** run `git pull origin main` into your branch before opening a PR, and at least every 2 hours.
- **Done** means:
  - the task's tests pass;
  - `python scripts/dev.py lint` passes;
  - the task is ticked in your `docs/status/<name>.md`;
  - the PR is merged.

### Contract changes

- **Additive, optional field** (with a default) in `contracts.py`/`contracts.ts`: Keshav may do it at any time. He opens an issue `[contract] <field>` that mentions both others, and merges.
- **Anything else** (rename, remove, type change, new required field, fusion rule change): raise it at the next sync point; all three agree; Keshav changes `docs/CONTRACT.md` and the code in one PR.
- An agent that finds the contract insufficient **stops that part**, opens an issue `[contract] ...`, writes it under "Blocked" in its status file, and moves on to the next independent task.

---

## 9. Commands (all from the repo root; work on Windows, macOS and Linux)

| What | Command |
|---|---|
| Setup | `python scripts/dev.py setup` (creates `.venv` with Python 3.11 via `uv`, installs both requirements files, `npm ci` in `web/`, copies `.env.example` to `.env`, runs both model fetch scripts) |
| Server | `python scripts/dev.py server` (uvicorn `pulselens.api.main:app` on 127.0.0.1:8000, reload) |
| Web | `python scripts/dev.py web` (Vite on :5173; proxies `/api` to :8000) |
| HTTPS for phones | `python scripts/dev.py tunnel` (cloudflared quick tunnel to :5173; prints the `https://….trycloudflare.com` URL) |
| Python tests | `python scripts/dev.py test` (`pytest server/tests`) |
| Web tests | `python scripts/dev.py test-web` (`tsc --noEmit` + `vitest run`) |
| Browser e2e | `python scripts/dev.py e2e` (Playwright, Chromium with a fake camera) |
| Lint | `python scripts/dev.py lint` (ruff + eslint) |
| Analyse one session | `python -m pulselens.analysis data/sessions/<id> --plots` |
| Evaluate | `python -m eval.run --sessions data/sessions --out eval/out` |
