# Status: Yash

Only Yash (and Yash's agent) edits this file. Newest notes first in each section.

## Tasks
- [ ] Y0
- [x] Y1
- [x] Y2: preflight/probe/face/quality/env; probe skips 1000x750 when resizeMode is unsupported (Safari, all iOS, Firefox); `controls` drops stream keys (width, height, frameRate, deviceId...)
- [x] Y3
- [x] Y4 (PR #24): uploader retries only on a network error, 5xx or timeout, with the same batch_seq; a 409 session_complete on a retry counts as success. The please_retry button only tells the customer to ask the agent (no API for a new link; needs Keshav). e2e full flow with Chrome's fake camera: preflight measured ~21 fps and no face, so the plan is CONSTRAINED; 251-261 frames in 13 batches, result in under 40 s. Uploader retries keep the same batch_seq (works with or without PR #22).
- [x] Y5 (PR #26): the ring fills at 20° from the resting yaw (median of the first 300 ms); guidance only, never a check. Falls back to the text prompt without the face tracker.
- [x] Y6 (PR #27): coaching thresholds: light < 40; backlight when outside-face luma > 2× face and ≥ 100; closer < 0.02 of the frame; shoulders when the face box bottom > 0.75; still when blur < first-1 s median / 2. Lenient starting points, tune on set A only. Up to 3 rounds of 3 s, then the flow continues. NO_FLASH skips the colour steps (skip_reason "no_flash") and shows "The agent will ask you a few questions." en + hi from navigator.language, with a toggle. With the fake camera (no face) "Move closer" fires, so e2e takes ~35-47 s per flow; the e2e waits are now 90 s (test 150 s) instead of 40 s.
- [ ] Y7 (PR #30, code done; real-device testing waits for Y0): `startTap()` in `web/src/capture/device.ts` runs synchronously from the Start click (Android fullscreen + portrait lock, wake lock re-acquired on visibilitychange, iOS motion permission); the fullscreen overlay is 100dvh (100vh fallback) for iPhone; all released at result, error or unmount. Desktop fullscreen stays in `chooseOverlayMode`.
- [x] Y8 (PR #25): /lab operator form (P/D codes, light, kind, tool, set, consent ref; no names; last settings remembered) → hand-off → the same capture screens → "Recording saved" + "Record another". The integration PR moves the capture screens into `web/src/customer/CaptureFlow.tsx`, used by both /customer and /lab, so the lab gets coaching, Hindi and the ring too.
- [x] Y9 (PR #31): fps drop = grabber `fpsOver(2000)` < 12 skips the remaining colour steps with "fps_drop" (sticky; the turn still runs; no verdict in the first 2 s). "Weak connection, still sending…" (en + hi) after 2 failed batches; the 15 s flush cap is unchanged. Camera errors: NotAllowed/Security → denied, NotFound → missing, NotReadable/Abort → busy, Overconstrained/other → camera_error; no retry. `?lock=1` locks before t0 and restores after the challenge.
- [x] T18 (#71): `capture/util.ts` holds `median`, `sleep`, `nextFrame`, `frameTime` and `FrameClock`; quality and flash re-export median and sleep so existing imports keep working. Deleted the dead "no_flash" skip and `opts.shouldSkipLight` (NO_FLASH plans get no colour steps). The grabber's fps median stays its own upper median (`xs[n >> 1]`, no averaging), so that number is unchanged. turn.ts's old median gave NaN on an empty list, but TurnMeter never calls it with one. The session test now only checks that NO_FLASH asks the agent's questions.
- [x] Y10 (PR #29): `web/e2e/support/bundle_to_y4m.py` writes `data/e2e-fixtures/replay.y4m` (gitignored). The `@real-analysis` replay test starts its own real-analysis server on :8001 and routes /api to it, so playwright.config.ts is unchanged; it skips without REPLAY_SESSION_DIR. Plumbing verified on a fake-camera session (replay → real analysis → decision.json); the final assertion waits for the agent /result fix (PR #23).
- [x] T17 (#70): `CaptureState` is a tagged union (`result` carries `message: CustomerMessage`, `error` carries `error: CaptureErrorDetail | "no_token"`); `detail`, both `includes()` guards and their casts are gone. `renderResult`/`renderError` get the narrowed state. Pure refactor; e2e deferred to the coordinator (shared ports across worktrees).
- [x] T19 (#72): `runPrompt(ctx, durationMs, show)` in `capture/turnPrompt.ts` is the one prompt skeleton (raise self-view, show, 2 frames -> painted, hold, hide, 2 frames -> ended); the text and ring prompts both use it. The session's one face tracker is a new `CaptureSessionDeps.faceTracker` passed to the prompt factory as `ctx.faceTracker`, so MediaPipe loads once per page (spy test). A null tracker falls back to the text prompt, as a rejected one did.

## Decisions
- Y9: OverconstrainedError maps to camera_error ("could not start your camera"), not camera_missing. The exposure lock is held for the whole challenge, turn included, because runChallenge has no hook after the last colour step.
- Y5-Y8: preflight and coaching share one face tracker; the turn prompt loads its own (could share it later). `CaptureFlow` (sessionId, token, className, data, renderResult, renderError) is the one place for the capture screens; the lab keeps the consent screen because its Start click is the user gesture (fullscreen) and the person should see the notice and the no-flash choice.
- Y4: "Ask the agent for a new link" (please_retry) has no API row, so the button only tells the customer to ask the agent on the call. The v1 turn prompt is `textTurnPrompt` in `web/src/capture/turnPrompt.ts`, passed to CaptureSession as `turnPrompt`; Y5 swaps it for the ring.
- Y1: stats().clock reports the latest frame's time source (per-frame fallback per CONTRACT §1); frames failing to encode are dropped with a warning, so idx can have gaps but stays strictly increasing.

## Measurements
- Y9 e2e (Chrome as BRAVE_PATH, customer.spec + lab.spec): 6/6 in 2.6 min.
- Y10 replay plumbing on a fake-camera session: the converter wrote 279 frames at the median 21 fps (399 at --fps 30); real analysis gave RETRY_STEP_UP / fresh_challenge, with family B flagging 13% repeated frames.
- Y5-Y8 integration e2e (Chrome fake camera, coaching on): full flow 45 s, lab recording 47 s, no-flash 20 s, no score leaks 35 s, 360px 39 s.

## Blocked
- Y10: GET /api/sessions/{id}/result returns 500 on main (agent.py calls SessionStore.load_json / expired, which the K2 review renamed). Keshav's K7 follow-up (PR #23) fixes it; the replay assertion needs it.

## Needs a human
- Y10: record one genuine, consented session on /lab (it lands in data/sessions/<id>), run `python scripts/fetch_models.py`, stop the dev servers, then from web/: `$env:REPLAY_SESSION_DIR="data/sessions/<id>"; npx playwright test --project=brave --grep "@real-analysis"`. Check the replay is flagged by light.response, not only by repeated frames.
- Y9: open /customer?lock=1 on the laptop webcam in a dim room and record the fps with and without it under Measurements (the old repo measured 10.4 fps unlocked). The lock only engages when measured fps < 27 and the camera exposes exposureMode.
- Y9: 5 budget-Android sessions in a dim room; record fps, mode and outcome for each.
- Y7: device checklist through the tunnel on Android Chrome, iPhone Safari, laptop Chrome and laptop + USB webcam (see PR #30): clock source, median fps, controls, probe results, overlay looked right, prompt readable, fullscreen exits at the end, page_hidden skip, iPhone motion prompt. One session per device must reach a result on the console.
- e2e: dev.py runs npx through cmd, so `-g "a|b"` breaks on Windows; pass spec files instead (`customer.spec lab.spec`).
- Y6: Hindi strings: TODO native-speaker check (`web/src/customer/strings.ts`).
- Y5-Y8 e2e: needs Brave, or `npx playwright install chromium`, or BRAVE_PATH pointing at Chrome. Run e2e one at a time (it starts its own server on :8000 and Vite on :5173).
- Y4 e2e: Brave is not installed on this laptop. I ran it with `BRAVE_PATH="C:/Program Files/Google/Chrome/Application/chrome.exe" python scripts/dev.py e2e --project=brave`, and all 4 customer tests passed. Plain `python scripts/dev.py e2e` also runs the opt-in `chromium` project, which fails until someone runs `npx playwright install chromium` in `web/`: Playwright wants build 1248, and only 1228 and 1243 are installed. The 4 console.spec failures are the known agent API issue (PR #23).
- Y2: verify the yaw sign on a laptop: run the face tracker, turn to your own left, expect positive `yawDeg`; record the result here (flip `YAW_SIGN` in `web/src/capture/face.ts` if negative). Run `python scripts/fetch_web_models.py` first.
- Y3 lock flag (Y9): test `?lock=1` on the laptop webcam in a dim room; record fps with and without it under Measurements.
