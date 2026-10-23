# Status: Yash

Only Yash (and Yash's agent) edits this file. Newest notes first in each section.

## Tasks
- [ ] Y0
- [x] Y1
- [x] Y2: preflight/probe/face/quality/env; probe skips 1000x750 when resizeMode is unsupported (Safari, all iOS, Firefox); `controls` drops stream keys (width, height, frameRate, deviceId...)
- [x] Y3
- [x] Y4: e2e full flow with Chrome's fake camera: preflight measured ~21 fps and no face, so the plan is CONSTRAINED; 251-261 frames in 13 batches, result in under 40 s. Uploader retries keep the same batch_seq (works with or without PR #22).
- [ ] Y5
- [ ] Y6
- [ ] Y7
- [ ] Y8
- [ ] Y9
- [ ] Y10

## Decisions
- Y4: "Ask the agent for a new link" (please_retry) has no API row, so the button only tells the customer to ask the agent on the call. The v1 turn prompt is `textTurnPrompt` in `web/src/capture/turnPrompt.ts`, passed to CaptureSession as `turnPrompt`; Y5 swaps it for the ring.
- Y1: stats().clock reports the latest frame's time source (per-frame fallback per CONTRACT §1); frames failing to encode are dropped with a warning, so idx can have gaps but stays strictly increasing.

## Measurements

## Blocked

## Needs a human
- Y4 e2e: Brave is not installed on this laptop. I ran it with `BRAVE_PATH="C:/Program Files/Google/Chrome/Application/chrome.exe" python scripts/dev.py e2e --project=brave`, and all 4 customer tests passed. Plain `python scripts/dev.py e2e` also runs the opt-in `chromium` project, which fails until someone runs `npx playwright install chromium` in `web/`: Playwright wants build 1248, and only 1228 and 1243 are installed. The 4 console.spec failures are the known agent API issue (PR #23).
- Y2: verify the yaw sign on a laptop: run the face tracker, turn to your own left, expect positive `yawDeg`; record the result here (flip `YAW_SIGN` in `web/src/capture/face.ts` if negative). Run `python scripts/fetch_web_models.py` first.
- Y3 lock flag (Y9): test `?lock=1` on the laptop webcam in a dim room; record fps with and without it under Measurements.
