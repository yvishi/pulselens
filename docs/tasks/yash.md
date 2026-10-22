# Yash: applicant device, capture and customer screens (Y0 to Y10)

**You own:** the applicant-device column of the architecture. That is the capture SDK (camera, clock, frame grabber, JPEG upload), the quality preflight with the mode-switch probe, the adaptive challenge rendering (colour light and head turn), coaching, the no-flash path, the customer screens, the Lab recording screen, and the browser end-to-end tests.

**Your paths:** `web/src/capture/**`, `web/src/customer/**`, `web/src/lab/**`, `web/e2e/customer.spec.ts`, `web/e2e/lab.spec.ts`, `web/e2e/support/**`, `web/e2e/fixtures/**`, `scripts/fetch_web_models.py`. Never edit `web/package.json`, `App.tsx`, `contracts.ts` or `api/client.ts`: ask Keshav with an issue.

**Before each task:** read the CONTRACT sections the task names.

**After each task:**
- Run `python scripts/dev.py test-web` and `lint` (and `e2e` from Y4 on).
- Tick the task in `docs/status/yash.md`.
- Open a PR and merge it (never delete the branch).

**Rules that bite in your area:**
- **One clock.** `performance.now()` only (ESLint bans `Date.now`). Every time on the wire is ms since `t0` (CONTRACT §1).
- **The customer never sees a score, family, check or outcome.** Only `CustomerStatus.message`, mapped to friendly text.
- **Mobile first.** Every customer screen works at 360 px wide on Android Chrome, with no sideways scroll.
- **Photosensitivity safety.** At most 3 colour changes per second; no saturated red; a no-flash choice before any flashing.
- **The camera frames are the evidence.** Upload exactly what the camera delivered (scaled and JPEG-encoded); no filters.

**Port from the old repo** (`../PulseLensFinal-ref/packages/capture/src/`). Each file is small and tested there; port its logic and tests into `web/src/capture/`, simplifying to this contract:

| Old file | What to take |
|---|---|
| `camera.ts` | `openCamera(video)`, `stopCamera()` (getUserMedia constraints) |
| `clock.ts` | `now()` |
| `grabber.ts` | `FrameGrabber` (rVFC / VideoFrame / rAF fallback, `fitSize`, stats) |
| `encoder.ts`, `encoder.worker.ts` | `createEncoder()` (OffscreenCanvas JPEG in a worker) |
| `probe.ts` | `runProbe()` (mode-switch probe) |
| `colour.ts` | `isoluminantColour(hueDeg, Y=0.5)`, `neutralColour()`, sRGB helpers |
| `light.ts`, `flash.ts` | `LightOverlay` (fullscreen/border), `FlashLimiter` |
| `lock.ts` | `lockForLight()`: lock exposure at 33 ms when measured fps < 27 |
| `coaching.ts` | `meanLuma`, `laplacianVariance`, `coachTips` |
| `uploader.ts` | `FrameUploader` (batching, queue limit) |
| `details.ts`, `env.ts` | browser/OS parsing, gyro detection, secure-context error |

---

## Y0. Device prep (human, before H0 and H0–1)

- [ ] `cloudflared` installed; `cloudflared tunnel --url http://localhost:5173` opened from an Android phone on mobile data.
- [ ] Devices charged and labelled: Android phone(s) `D01…`, iPhone, laptop webcam, USB webcam. Write the device list in `docs/status/yash.md`.
- [ ] Old repo cloned to `../PulseLensFinal-ref`; read the files in the table above.

---

## Y1. Camera, clock, grabber, encoder (H1–3)

**Files:**
- `web/src/capture/clock.ts`, `camera.ts`, `grabber.ts`, `encoder.ts`, `encoder.worker.ts`, `constants.ts`
- tests: `grabber.test.ts`, `clock.test.ts`

**Interfaces you produce:**
```ts
export const now: () => number;                                    // performance.now()
export interface OpenCamera { stream: MediaStream; track: MediaStreamTrack; settings: MediaTrackSettings }
export async function openCamera(video: HTMLVideoElement, size: [number, number]): Promise<OpenCamera>;
// getUserMedia({ video: { width: {ideal: w}, height: {ideal: h}, frameRate: {ideal: 30}, facingMode: "user" }, audio: false })
export function stopCamera(cam: OpenCamera | null, video?: HTMLVideoElement): void;
export interface GrabbedFrame { idx: number; t_ms: number; w: number; h: number; jpeg: Blob }
export class FrameGrabber {
  constructor(video: HTMLVideoElement, opts: { size: [number, number]; jpegQuality: number; t0: number;
    onFrame: (f: GrabbedFrame) => void });
  start(): void; stop(): void;
  stats(): { frames: number; medianFps: number; droppedRatio: number; clock: "captureTime" | "expectedDisplayTime" | "now" };
}
```
- `constants.ts` mirrors `config.yaml` `capture` (desktop 640×480, mobile 480×360, JPEG 0.9, batch 1000 ms).
- Frame time: `metadata.captureTime ?? metadata.expectedDisplayTime ?? now`, minus `t0`.
- `droppedRatio` comes from `metadata.presentedFrames` gaps.

**Tests:**
- `grabber.test.ts::fitSize keeps aspect`.
- `uses captureTime when present`: a fake rVFC callback with metadata → `t_ms` = captureTime − t0.
- `idx strictly increasing`.
- `medianFps from intervals`: intervals of 33.3 ms → 30 ± 0.5.

---

## Y2. Quality preflight and mode probe (H2–5)

**Read:** CONTRACT §3 `Preflight`, `ModeProbe`.

**Files:**
- `web/src/capture/preflight.ts`, `probe.ts`, `quality.ts`, `face.ts`, `env.ts`
- tests: `preflight.test.ts`, `quality.test.ts`, `probe.test.ts`
- `scripts/fetch_web_models.py`

**Interfaces:**
```ts
export async function runPreflight(video: HTMLVideoElement, cam: OpenCamera, opts: { noFlashRequested: boolean }): Promise<Preflight>;
// ~3 s: measures fps and dropped frames over >= 2 s; blur and brightness on a 160x120 downscale every 200 ms (median);
// one face detection; reads track.getCapabilities() keys into `controls`; detects gyro; runs the probe.
export async function runProbe(track: MediaStreamTrack, video: HTMLVideoElement): Promise<ModeProbe[]>;
// requested modes: [1280,720,30], [640,480,30], [1000,750,24]; settle 1000 ms each; restore the working constraints after.
// Skip [1000,750,24] on Safari and Firefox (no resizeMode) and report it with accepted=false, delivered=null.
export interface FaceTracker { detect(video: HTMLVideoElement, tMs: number): { found: boolean; box: [number, number, number, number] | null; yawDeg: number | null } }
export async function createFaceTracker(): Promise<FaceTracker>;
// @mediapipe/tasks-vision FaceLandmarker, VIDEO mode, outputFacialTransformationMatrixes: true;
// model from /models/face_landmarker.task, wasm from /models/wasm (copied by scripts/fetch_web_models.py).
// yaw from the transformation matrix: yawDeg = atan2(m[8], m[10]) in degrees, sign per CONTRACT §1 (positive = person's own left).
export function meanLuma(d: Uint8ClampedArray, w: number, h: number): number;
export function laplacianVariance(d: Uint8ClampedArray, w: number, h: number): number;
```
- **`fetch_web_models.py`** downloads, if missing:
  - `https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task` into `web/public/models/`;
  - copies `web/node_modules/@mediapipe/tasks-vision/wasm/*` into `web/public/models/wasm/`.
- **Verify the yaw sign** on yourself in front of a laptop (turn to your own left, expect a positive yaw). Record it in your status file. The server side (Ganeev) uses the same convention.

**Tests:**
- `quality.test.ts`:
  - `meanLuma of a uniform 128 image is 128`;
  - `laplacianVariance of a flat image is 0 and of a checkerboard is > 1000`.
- `probe.test.ts` (port the old simulated-camera test):
  - an accepted mode records `delivered` and `switch_ms`;
  - Safari skips the unusual mode.
- `preflight.test.ts`: with a stubbed grabber and face tracker, `runPreflight` returns every `Preflight` field with the right types.

---

## Y3. Challenge renderer: colour light and turn prompt (H3–7)

**Read:** CONTRACT §3 `Challenge`, `ChallengeEvent`; `docs/ARCHITECTURE.md` "Active light challenge".

**Files:**
- `web/src/capture/colour.ts`, `overlay.ts`, `challenge.ts`, `lock.ts`
- tests: `colour.test.ts`, `challenge.test.ts`

**Interfaces:**
```ts
export function isoluminantColour(hueDeg: number, Y?: number): [number, number, number];   // sRGB 0..1, Y default 0.5
export function neutralColour(Y?: number): [number, number, number];
export class LightOverlay {                       // full-screen <div> above everything; on desktop: requestFullscreen(),
  constructor(root: HTMLElement, mode: "fullscreen" | "border");   // falls back to a border of 18% of the short side
  paint(rgb: [number, number, number]): Promise<number>;          // sets the colour, resolves with painted_t_ms (double rAF, minus t0)
  clear(): Promise<number>;                                        // back to neutral; resolves with ended_t_ms
  dispose(): void;
}
export async function runChallenge(ch: Challenge, deps: {
  overlay: LightOverlay; t0: number; showTurnPrompt: (dir: "left" | "right", durationMs: number) => Promise<{ painted: number; ended: number }>;
  shouldSkipLight: () => string | null;            // returns a skip reason ("fps_drop", "page_hidden") or null
}): Promise<ChallengeEvent[]>;
// 1) neutral for baseline_ms, 2) each step at its start_offset_ms after the baseline; colour: paint, wait dwell_ms, clear;
// turn: showTurnPrompt. A skipped step gives status "skipped" with its reason. Never more than 3 colour changes per second.
```
- **Port `light.ts`, `flash.ts`, `colour.ts`.**
- **Safety assertions:**
  - `runChallenge` throws before painting if any hue is in [345, 15] (that would be a server bug);
  - a `FlashLimiter` ensures ≥ 334 ms between colour changes.
- **Prompt text on the coloured overlay** must stay readable: white text with a dark 50% backdrop.
- **Port `lock.ts`** (exposure lock at 33 ms when fps < 27, where `controls` include `exposureMode`; restored after the light steps) as an **experiment behind a flag** (`?lock=1`). It is cut-list item 6.

**Tests:**
- `colour.test.ts`:
  - every hue in `[40, 80, 140, 200, 250, 300]` gives a colour whose relative luminance is within ±5% of 0.5;
  - all channels lie in 0..1.
- `challenge.test.ts` (fake timers, fake overlay):
  - the events come back in step order;
  - each painted ≥ the step's scheduled time;
  - a skip reason gives `status: "skipped"` and `painted_t_ms: null`;
  - a red hue throws;
  - changes per second never exceed 3.

---

## Y4. Uploader and customer flow v1 (H5–8, needed for S1)

**Read:** CONTRACT §2 (every customer row).

**Files:**
- `web/src/capture/uploader.ts`, `web/src/capture/session.ts`
- `web/src/customer/CustomerPage.tsx` (replace the placeholder), `web/src/customer/steps/*.tsx`, `web/src/customer/strings.ts`
- `web/e2e/customer.spec.ts`, `web/e2e/support/*`

**Interfaces:**
```ts
export class FrameUploader {   // batches GrabbedFrames every 1000 ms (<= 30 per batch) into postFrames(); keeps a queue of <= 90;
  constructor(opts: { sessionId: string; token: string; batchMs: number });   // retries a failed batch twice with 500 ms backoff
  push(f: GrabbedFrame): void; flush(): Promise<void>; stats(): { sent: number; dropped: number; failedBatches: number };
}
export type CustomerPhase = "consent" | "camera" | "preflight" | "coaching" | "ready" | "challenge" | "uploading" | "waiting" | "result" | "error";
export class CaptureSession {   // drives the whole flow; React only renders its state
  constructor(opts: { sessionId: string; token: string; video: HTMLVideoElement; overlayRoot: HTMLElement; onState: (s: { phase: CustomerPhase; detail?: string }) => void });
  start(noFlashRequested: boolean): Promise<void>;   // camera -> preflight (postPreflight) -> getChallenge -> grabber + runChallenge -> postEvents -> flush -> completeSession -> poll getStatus every 1 s
}
```

**Customer screens (`/customer/:sessionId?t=<token>`):**
1. **Consent and notice.** "Your screen will show a few soft colours and ask you to turn your head. This takes about 20 seconds." Two buttons: **Start** and **I'd rather not see flashing colours** (sets `noFlashRequested`).
2. **Camera.** The permission request. If it is denied: "We need your camera for video-KYC. You can also continue with the agent." No retry loop.
3. **Preflight + coaching** (Y6 adds tips).
4. **Challenge.** The overlay, plus a small self-view (top corner, ≤ 25% width) during the turn only.
5. **Uploading / waiting:** "Please wait…".
6. **Result**, mapped from `message`:
   - `continue` → "Thank you, you can continue the call."
   - `please_retry` → "Let's try that once more." plus a button that asks the agent for a new link.
   - `please_wait` → "Please wait for the agent."
   - `assisted_route` → "The agent will help you complete KYC."
   - **Never** a score.

**e2e** (`customer.spec.ts`, Chromium fake camera, real server with `PULSE_FAKE_ANALYSIS=1`):
- `full flow reaches result`:
  - create a session through the API and open its `customer_url`;
  - click Start;
  - within 40 s the result text "Thank you, you can continue the call." appears;
  - the bundle has ≥ 100 frames with strictly increasing `t_ms`, and events for every challenge step.
- `no-flash path`:
  - the "I'd rather not" button gives a plan `NO_FLASH`;
  - no `colour` event has `status: "shown"`.
- `no score leaks`: intercept every response on the customer page; none contains `"risk"`, `"family"` or `"outcome"`.
- `360px no sideways scroll` on every customer phase.

**S1:** with Keshav, run one real laptop session end to end.

---

## Y5. Head-turn prompt (H8–12)

**Files:**
- `web/src/customer/steps/TurnPrompt.tsx`
- `web/src/capture/turn.ts`
- test: `turn.test.ts`

**Build:**
- A large arrow and the text "Turn your head to your LEFT, then back to the centre" (or RIGHT). The direction is the person's own.
- On a front camera, the self-view is mirrored, so the arrow points to the **same side of the screen** as the person's own direction (left arrow for their left).
- A live progress ring driven by `FaceTracker.yawDeg`: full at 20° in the requested direction.
- After `duration_ms` the prompt ends, whatever happened. **The client never judges the turn; the server does.** The ring is guidance only.
- `showTurnPrompt` resolves with `{painted, ended}` for the event.

**Tests:**
- `turn.test.ts::progress is 0 at yaw 0, 1 at 20 deg in the requested direction, 0 in the wrong direction`.
- `arrow side matches mirrored view`.

---

## Y6. Coaching, no-flash and languages (H10–14)

**Files:**
- `web/src/capture/coaching.ts`
- `web/src/customer/steps/Coaching.tsx`
- `web/src/customer/strings.ts` (EN + HI)

**Build:**
- **Coaching** (port `coaching.ts`):
  - **Tips**, at most 2 at a time:
    - "Face the light" (brightness < 40);
    - "Too bright behind you" (luma outside the face ≫ the face's);
    - "Move closer" (`face_fraction < 0.02`);
    - "Show your shoulders" (no room below the chin: the face box bottom > 75% of the frame height);
    - "Hold still" (blur below the median of the first 1 s / 2).
  - **Rounds:** up to 3 rounds of 3 s each, then continue anyway. The server's planner decides the mode.
- **Strings:**
  - `strings.ts` has `en` and `hi` for every customer string;
  - the language follows `navigator.language` (starts with `hi` → Hindi), with an EN/HI toggle on the consent screen;
  - Hindi text written plainly; mark it `// TODO: native-speaker check` in your status file, not in code.
- **No-flash path:**
  - the plan is NO_FLASH → skip all colour steps and run only the turn;
  - then show "The agent will ask you a few questions."

**Tests:**
- `coaching.test.ts`: one test per tip with synthetic metrics.
- `strings.test.ts`: every key exists in both languages.

---

## Y7. Phones (H12–18)

**Build:**
- **Android Chrome:**
  - `requestFullscreen()` on Start (a user gesture);
  - `navigator.wakeLock.request("screen")`;
  - the overlay is full screen, mobile size 480×360.
- **iPhone Safari:**
  - no Fullscreen API on iPhone, so the overlay covers the viewport (`position: fixed; inset: 0; 100dvh`);
  - `playsinline` and `muted` on the video;
  - the probe skips the unusual mode;
  - no `captureTime` (falls back to `expectedDisplayTime`).
- **Page hidden** (the user switches app) → the remaining light steps are skipped with the reason `page_hidden`.
- **Test on real devices through the tunnel:** Android Chrome, iPhone Safari, laptop Chrome, laptop + USB webcam. For each device, write in `docs/status/yash.md`:
  - clock source;
  - median fps;
  - controls;
  - probe results;
  - whether the overlay looked right and the prompt was readable.

**Done when:** one session per device reaches a result on the console.

---

## Y8. Lab recording page (H12–16)

**Files:**
- `web/src/lab/LabPage.tsx` (replace the placeholder), `web/src/lab/OperatorForm.tsx`
- `web/e2e/lab.spec.ts`

**Build:**
- **Operator form** → `Label`:
  - person `P01…` (pattern-validated);
  - device `D01…`;
  - light (bright/normal/dim/tube);
  - kind (genuine/replay_screen/virtual_camera/live_swap/photo_animation);
  - tool (free text, required unless kind is genuine);
  - set (A/B);
  - consent reference (required).
- **Continue** → `createSession({ label })` → hand the device to the person → the same `CaptureSession` flow.
- **End screen:** "Recording saved", the session id in large text, and a button "Record another (same settings)".
- **The form never asks for a name.**

**Tests:** `lab.spec.ts`:
- a missing consent reference blocks Continue;
- a full recording writes `session.json` with the label.

---

## Y9. Capture hardening (H18–30)

**Build:**
- **fps-drop downgrade:**
  - while the challenge runs, if the grabber's fps over the last 2 s drops below 12, `shouldSkipLight()` returns `"fps_drop"` for the remaining colour steps;
  - the turn still runs.
- **Exposure lock** (Y3 flag): test it on the laptop webcam in a dim room with `?lock=1`. Record the fps with and without it in your status file (the old repo measured 10.4 fps unlocked in a dim room; the lock is unconfirmed).
- **Network:**
  - the uploader shows "Weak connection, still sending…" after 2 failed batches;
  - `completeSession` waits for `flush()` with a 15 s cap.
- **Camera errors:** NotAllowedError, NotFoundError and NotReadableError each map to a clear message.
- **Budget Android in a dim room:** run 5 sessions; record fps, mode and outcome.

**Tests:**
- `challenge.test.ts::fps drop skips the remaining colour steps but not the turn`.
- `uploader.test.ts::retries twice then counts a failed batch`.

---

## Y10. End-to-end suite and replay attack fixture (H24–32)

**Build:**
- **Replay e2e** (needs Ganeev's real analysis on `main`, so no `PULSE_FAKE_ANALYSIS` here):
  - Convert one **genuine** recorded session's frames into a `.y4m` (port the old `scripts/bundle_to_y4m.py` into `web/e2e/support/bundle_to_y4m.py`).
  - Run the customer flow with Chromium's `--use-file-for-fake-video-capture=<y4m>`.
  - Expected (hypothesis): `light.response` flags (the replay can't answer today's colours).
  - Keep this test tagged `@real-analysis`; it runs with `npx playwright test --grep @real-analysis`.
- **Clean up:** e2e uses `PULSE_DATA_DIR=data/e2e`, never `data/sessions`.

**Tests:**
- `customer.spec.ts @real-analysis replay is not PASS`: the outcome on `/result` (read through the agent API in the test) is not PASS.

---

## Sync duties
- **S1:** a real laptop session end to end, together with Keshav.
- **S2:** the device table in your status file is filled for every device you have.
- **Recording (H10–H30):** genuine sessions on `/lab` (see `docs/PLAN.md` section 5). Target ≥ 60.
