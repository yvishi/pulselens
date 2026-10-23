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
- [ ] Y7
- [x] Y8 (PR #25): /lab operator form (P/D codes, light, kind, tool, set, consent ref; no names; last settings remembered) → hand-off → the same capture screens → "Recording saved" + "Record another". The integration PR moves the capture screens into `web/src/customer/CaptureFlow.tsx`, used by both /customer and /lab, so the lab gets coaching, Hindi and the ring too.
- [ ] Y9
- [ ] Y10

## Decisions
- Y5-Y8: preflight and coaching share one face tracker; the turn prompt loads its own (could share it later). `CaptureFlow` (sessionId, token, className, data, renderResult, renderError) is the one place for the capture screens; the lab keeps the consent screen because its Start click is the user gesture (fullscreen) and the person should see the notice and the no-flash choice.
- Y4: "Ask the agent for a new link" (please_retry) has no API row, so the button only tells the customer to ask the agent on the call. The v1 turn prompt is `textTurnPrompt` in `web/src/capture/turnPrompt.ts`, passed to CaptureSession as `turnPrompt`; Y5 swaps it for the ring.
- Y1: stats().clock reports the latest frame's time source (per-frame fallback per CONTRACT §1); frames failing to encode are dropped with a warning, so idx can have gaps but stays strictly increasing.

## Measurements
- Y5-Y8 integration e2e (Chrome fake camera, coaching on): full flow 45 s, lab recording 47 s, no-flash 20 s, no score leaks 35 s, 360px 39 s.

## Blocked

## Needs a human
- Y6: Hindi strings: TODO native-speaker check (`web/src/customer/strings.ts`).
- Y5-Y8 e2e: needs Brave, or `npx playwright install chromium`, or BRAVE_PATH pointing at Chrome. Run e2e one at a time (it starts its own server on :8000 and Vite on :5173).
- Y4 e2e: Brave is not installed on this laptop. I ran it with `BRAVE_PATH="C:/Program Files/Google/Chrome/Application/chrome.exe" python scripts/dev.py e2e --project=brave`, and all 4 customer tests passed. Plain `python scripts/dev.py e2e` also runs the opt-in `chromium` project, which fails until someone runs `npx playwright install chromium` in `web/`: Playwright wants build 1248, and only 1228 and 1243 are installed. The 4 console.spec failures are the known agent API issue (PR #23).
- Y2: verify the yaw sign on a laptop: run the face tracker, turn to your own left, expect positive `yawDeg`; record the result here (flip `YAW_SIGN` in `web/src/capture/face.ts` if negative). Run `python scripts/fetch_web_models.py` first.
- Y3 lock flag (Y9): test `?lock=1` on the laptop webcam in a dim room; record fps with and without it under Measurements.
