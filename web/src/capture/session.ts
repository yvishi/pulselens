/**
 * One customer (or Lab) capture session, start to result. React only renders the state this reports.
 *
 * camera -> runPreflight (+ coaching measure) -> up to 3 coaching rounds, then runPreflight again -> postPreflight (Plan) -> getChallenge -> FrameGrabber (t0 = challenge start) + runChallenge
 * on a LightOverlay (exposure locked around it behind ?lock=1) -> postEvents -> uploader.flush() (15 s cap) -> completeSession -> getStatus every 1 s until done.
 *
 * The server's plan decides what runs: a NO_FLASH plan (or run_light false) gets a challenge with no colour steps,
 * so nothing is painted and only the turn runs; the agent then asks a few questions.
 * completeSession is never called while a frame batch is in flight (the uploader is flushed or stopped first).
 *
 * Hardening (Y9): an fps drop (< 12 fps over the last 2 s) skips the remaining colour steps ("fps_drop"), never the
 * turn; after 2 failed frame batches the state carries weakConnection (the screen says "Weak connection, still
 * sending"); each getUserMedia failure maps to one error detail, with no retry loop.
 * Every dependency is injectable, so the Lab page and the tests reuse the same flow.
 */
import * as client from "../api/client";
import { ApiError } from "../api/client";
import type { Challenge, ChallengeEvent, CustomerMessage, CustomerStatus, FrameBatchMeta, Plan, Preflight } from "../contracts";
import { openCamera, stopCamera, type OpenCamera } from "./camera";
import { fpsDropSkip, runChallenge } from "./challenge";
import { COACH_ROUNDS, COACH_ROUND_MS, coachTips, createCoachMeter, type CoachMeter, type CoachTip } from "./coaching";
import { now } from "./clock";
import { DESKTOP_SIZE, JPEG_QUALITY, MOBILE_SIZE, UPLOAD_BATCH_MS } from "./constants";
import { platformOf, secureContextError } from "./env";
import { sleep } from "./flash";
import { FrameGrabber, type GrabberOptions, type GrabberStats } from "./grabber";
import { LightOverlay, chooseOverlayMode, type OverlayMode } from "./overlay";
import { createFaceTracker, type FaceTracker } from "./face";
import { lockForLight, shouldLock, type CameraLock } from "./lock";
import { PREFLIGHT_MS, runPreflight } from "./preflight";
import { withRetries } from "./retry";
import { textTurnPrompt, type TurnDirection, type TurnPromptFactory } from "./turnPrompt";
import { FrameUploader, type UploaderOptions, type UploaderStats } from "./uploader";

export type CustomerPhase =
  | "consent" | "camera" | "preflight" | "coaching" | "ready" | "challenge" | "uploading" | "waiting" | "result" | "error";

/**
 * Error details: "insecure" (no HTTPS / no camera API), "camera_denied", "camera_missing", "camera_busy",
 * "camera_error", "expired", "failed".
 */
export type CaptureErrorDetail =
  | "insecure" | "camera_denied" | "camera_missing" | "camera_busy" | "camera_error" | "expired" | "failed";

interface CaptureCommon {
  /** from the Plan, once known: the agent will ask a few questions (no-flash path, no face found) */
  agentQuestions?: boolean;
  /** coaching: at most 2 tips for this round */
  tips?: CoachTip[];
  /** set once 2 frame batches have failed: "Weak connection, still sending" (kept until the end) */
  weakConnection?: boolean;
}

/** result carries the CustomerStatus.message; error carries why ("no_token" comes from CaptureFlow, never the session). */
export type CaptureState = CaptureCommon &
  (
    | { phase: Exclude<CustomerPhase, "result" | "error"> }
    | { phase: "result"; message: CustomerMessage }
    | { phase: "error"; error: CaptureErrorDetail | "no_token" }
  );

export interface CaptureApi {
  postPreflight(id: string, token: string, body: Preflight): Promise<Plan>;
  getChallenge(id: string, token: string): Promise<Challenge>;
  postFrames(id: string, token: string, meta: FrameBatchMeta, jpegs: Blob[]): Promise<void>;
  postEvents(id: string, token: string, events: ChallengeEvent[]): Promise<void>;
  completeSession(id: string, token: string): Promise<void>;
  getStatus(id: string, token: string): Promise<CustomerStatus>;
}

/** The overlay as the session uses it (LightOverlay, or a fake in tests). */
export interface SessionOverlay {
  t0: number;
  paint(rgb: [number, number, number]): Promise<number>;
  clear(): Promise<number>;
  showPrompt(text: string | null): void;
  dispose(): void;
}

export interface SessionGrabber {
  start(): void;
  stop(): void;
  close(): void;
  stats(): GrabberStats;
  /** frames per second over the last ms, null until the grabber has run that long */
  fpsOver(ms: number): number | null;
}

export type SessionUploader = Pick<FrameUploader, "push" | "flush" | "stop" | "stats">;

export interface CaptureSessionDeps {
  api: CaptureApi;
  secureContextError: () => string | null;
  isMobile: () => boolean;
  openCamera: (video: HTMLVideoElement, size: [number, number]) => Promise<OpenCamera>;
  stopCamera: (cam: OpenCamera | null, video?: HTMLVideoElement) => void;
  runPreflight: (video: HTMLVideoElement, cam: OpenCamera, opts: { noFlashRequested: boolean }) => Promise<Preflight>;
  chooseOverlayMode: (desktop: boolean) => Promise<OverlayMode>;
  createOverlay: (root: HTMLElement, mode: OverlayMode, t0: number) => SessionOverlay;
  createGrabber: (video: HTMLVideoElement, opts: GrabberOptions) => SessionGrabber;
  createUploader: (opts: UploaderOptions) => SessionUploader;
  runChallenge: typeof runChallenge;
  createCoachMeter: (video: HTMLVideoElement) => CoachMeter;
  /** the session's one face tracker (null when it cannot load), shared by preflight, coaching and the turn prompt */
  faceTracker: () => Promise<FaceTracker | null>;
  /** whether to try the exposure lock (the ?lock=1 experiment) */
  shouldLock: (pf: Preflight) => boolean;
  lockForLight: (track: MediaStreamTrack, fps: number | null) => Promise<{ lock: CameraLock | null; restore: () => Promise<void> }>;
  now: () => number;
  sleep: (ms: number) => Promise<void>;
}

export interface CaptureSessionOptions {
  sessionId: string;
  token: string;
  video: HTMLVideoElement;
  overlayRoot: HTMLElement;
  onState: (s: CaptureState) => void;
  /** builds the turn prompt (default: textTurnPrompt; Y5 passes the ring prompt) */
  turnPrompt?: TurnPromptFactory;
  /** turn prompt text per direction (customer strings) */
  turnText?: (dir: TurnDirection) => string;
  deps?: Partial<CaptureSessionDeps>;
}

export const FLUSH_CAP_MS = 15_000;
export const POLL_MS = 1000;
/** Analysis has a 120 s timeout on the server; stop polling a little after it. */
export const MAX_POLLS = 180;
/** Time for the grabber's last encodes to reach the uploader after stop(). */
export const ENCODE_SETTLE_MS = 200;
/** Failed frame batches before the screen says the connection is weak. */
export const WEAK_AFTER_FAILED_BATCHES = 2;

const DEFAULT_TURN_TEXT = (dir: TurnDirection) => `Turn your head to your ${dir.toUpperCase()}, then back to the centre`;

/** One face tracker per page, shared by the preflight, the coaching meter and the turn prompt (loading it twice is slow). */
let sharedTracker: Promise<FaceTracker | null> | null = null;
const faceTracker = () => (sharedTracker ??= createFaceTracker().catch(() => null));

export const defaultDeps = (): CaptureSessionDeps => ({
  api: withRetries(client),
  secureContextError,
  isMobile: () => {
    const p = platformOf(navigator.userAgent, navigator.maxTouchPoints ?? 0);
    return p === "android" || p === "ios";
  },
  openCamera,
  stopCamera,
  runPreflight: (video, cam, opts) =>
    runPreflight(video, cam, opts, { faceTracker: async () => (await faceTracker()) ?? Promise.reject(new Error("no face")) }),
  chooseOverlayMode: (desktop) => chooseOverlayMode(desktop),
  createOverlay: (root, mode, t0) => new LightOverlay(root, mode, { t0 }),
  createGrabber: (video, opts) => new FrameGrabber(video, opts),
  createUploader: (opts) => new FrameUploader(opts),
  runChallenge,
  createCoachMeter: (video) => createCoachMeter(video, faceTracker()),
  faceTracker,
  shouldLock: (pf) => typeof location !== "undefined" && shouldLock(pf, location.search),
  lockForLight,
  now,
  sleep,
});

/**
 * Maps a getUserMedia failure to an error detail (one clear customer message each, no retry loop):
 * denied (NotAllowedError, SecurityError), no camera (NotFoundError), in use by another app (NotReadableError,
 * AbortError), anything else including OverconstrainedError (a camera exists but would not start) -> camera_error.
 */
export function cameraError(e: unknown): CaptureErrorDetail {
  const name = typeof e === "object" && e !== null ? (e as { name?: unknown }).name : undefined;
  if (name === "NotAllowedError" || name === "SecurityError") return "camera_denied";
  if (name === "NotFoundError") return "camera_missing";
  if (name === "NotReadableError" || name === "AbortError") return "camera_busy";
  return "camera_error";
}

class CameraFailed extends Error {
  constructor(readonly detail: CaptureErrorDetail) {
    super(detail);
  }
}

export class CaptureSession {
  private readonly deps: CaptureSessionDeps;
  private cam: OpenCamera | null = null;
  private grabber: SessionGrabber | null = null;
  private overlay: SessionOverlay | null = null;
  private uploader: SessionUploader | null = null;
  private state: CaptureState = { phase: "consent" };
  private started = false;
  private disposed = false;

  constructor(private readonly opts: CaptureSessionOptions) {
    this.deps = { ...defaultDeps(), ...opts.deps };
  }

  /** Upload counters, for coaching ("weak connection") and the Lab page. */
  uploadStats(): UploaderStats | null {
    return this.uploader?.stats() ?? null;
  }

  private set(next: CaptureState): void {
    if (this.disposed) return;
    // agentQuestions and weakConnection stick; tips and the result/error payload belong to one phase
    const { agentQuestions, weakConnection } = this.state;
    this.state = { agentQuestions, weakConnection, ...next };
    this.opts.onState(this.state);
  }

  /** Raises the weak-connection flag once, keeping the phase and everything else. */
  private onUploadStats(s: UploaderStats): void {
    if (this.disposed || this.state.weakConnection || s.failedBatches < WEAK_AFTER_FAILED_BATCHES) return;
    this.state = { ...this.state, weakConnection: true };
    this.opts.onState(this.state);
  }

  /** Call straight from the Start click: the overlay asks for fullscreen while the user gesture is live. */
  async start(noFlashRequested: boolean): Promise<void> {
    if (this.started) return;
    this.started = true;
    const d = this.deps;
    const { sessionId: id, token, video } = this.opts;
    if (d.secureContextError()) return this.set({ phase: "error", error: "insecure" });
    const mobile = d.isMobile();
    const size = mobile ? MOBILE_SIZE : DESKTOP_SIZE;
    const overlayMode = d.chooseOverlayMode(!mobile); // first, inside the gesture
    try {
      this.set({ phase: "camera" });
      this.cam = await d.openCamera(video, size).catch((e: unknown) => {
        throw new CameraFailed(cameraError(e));
      });

      const preflight = await this.preflightWithCoaching(this.cam, noFlashRequested);
      const plan = await d.api.postPreflight(id, token, preflight);
      const challenge = await d.api.getChallenge(id, token);

      this.set({ phase: "challenge", agentQuestions: plan.agent_questions });
      const noFlash = plan.mode === "NO_FLASH" || !plan.run_light;
      const events = await this.capture(challenge, size, await overlayMode, noFlash, preflight);

      this.set({ phase: "uploading" });
      await d.api.postEvents(id, token, events);
      await this.drainUploads();
      d.stopCamera(this.cam, video);
      this.cam = null;

      this.set({ phase: "waiting" });
      await d.api.completeSession(id, token);
      const message = await this.poll();
      this.set({ phase: "result", message });
    } catch (e) {
      if (!(e instanceof CameraFailed)) console.error("capture session failed", e);
      const error: CaptureErrorDetail =
        e instanceof CameraFailed ? e.detail : e instanceof ApiError && e.status === 410 ? "expired" : "failed";
      await this.uploader?.stop();
      this.set({ phase: "error", error });
    } finally {
      this.cleanup();
    }
  }

  /**
   * Preflight, measured alongside the coaching meter. If tips fire, up to 3 coaching rounds of 3 s (the tips stay up
   * while the next round measures), then continue anyway with a fresh preflight: the server's planner decides the mode.
   */
  private async preflightWithCoaching(cam: OpenCamera, noFlashRequested: boolean): Promise<Preflight> {
    const d = this.deps;
    const { video } = this.opts;
    this.set({ phase: "preflight" });
    const meter = d.createCoachMeter(video);
    const [first, metrics] = await Promise.all([
      d.runPreflight(video, cam, { noFlashRequested }),
      meter.measure(PREFLIGHT_MS).catch(() => null),
    ]);
    let tips = metrics ? coachTips(metrics) : [];
    if (!tips.length) return first;
    for (let round = 1; round <= COACH_ROUNDS && tips.length; round++) {
      this.set({ phase: "coaching", tips });
      const m = await meter.measure(COACH_ROUND_MS).catch(() => null);
      tips = m ? coachTips(m) : [];
    }
    this.set({ phase: "preflight" });
    return d.runPreflight(video, cam, { noFlashRequested });
  }

  /** Grabber + challenge on the overlay; returns the events. t0 is the challenge start. */
  private async capture(
    challenge: Challenge, size: [number, number], mode: OverlayMode, noFlash: boolean, preflight: Preflight,
  ): Promise<ChallengeEvent[]> {
    const d = this.deps;
    const { sessionId, token, video } = this.opts;
    // The ?lock=1 experiment: freeze exposure / white balance before t0, hand them back after the challenge.
    const lock = !noFlash && this.cam && d.shouldLock(preflight)
      ? await d.lockForLight(this.cam.track, preflight.measured_fps ?? null)
      : null;
    if (lock?.lock) console.info("camera lock", lock.lock);
    const t0 = d.now();
    const overlay = (this.overlay = d.createOverlay(this.opts.overlayRoot, mode, t0));
    const uploader = (this.uploader = d.createUploader({
      sessionId, token, batchMs: UPLOAD_BATCH_MS, postFrames: d.api.postFrames, onStats: (s) => this.onUploadStats(s),
    }));
    const grabber = (this.grabber = d.createGrabber(video, {
      size, jpegQuality: JPEG_QUALITY, t0, onFrame: (f) => uploader.push(f),
    }));
    grabber.start();
    const showTurnPrompt = (this.opts.turnPrompt ?? textTurnPrompt)({
      overlay, video, text: this.opts.turnText ?? DEFAULT_TURN_TEXT, faceTracker: d.faceTracker,
    });
    const fpsDrop = fpsDropSkip(grabber);
    const shouldSkipLight = () =>
      (typeof document !== "undefined" && document.hidden ? "page_hidden" : null) ?? fpsDrop() ?? null;
    try {
      return await d.runChallenge(challenge, { overlay, t0, showTurnPrompt, shouldSkipLight });
    } finally {
      await lock?.restore();
      grabber.stop();
      overlay.dispose();
      this.overlay = null;
    }
  }

  /** Lets the last encodes land, flushes with a 15 s cap, then stops the uploader (nothing in flight after this). */
  private async drainUploads(): Promise<void> {
    const d = this.deps;
    const uploader = this.uploader;
    if (!uploader) return;
    await d.sleep(ENCODE_SETTLE_MS);
    let timer: ReturnType<typeof setTimeout> | undefined;
    const cap = new Promise<void>((r) => (timer = setTimeout(r, FLUSH_CAP_MS)));
    await Promise.race([uploader.flush(), cap]);
    clearTimeout(timer);
    await uploader.stop();
  }

  /** getStatus every second until the analysis is done; network blips are retried. */
  private async poll(): Promise<CustomerMessage> {
    const d = this.deps;
    for (let k = 0; k < MAX_POLLS; k++) {
      try {
        const s = await d.api.getStatus(this.opts.sessionId, this.opts.token);
        if (s.state === "done") return s.message;
      } catch (e) {
        if (e instanceof ApiError && e.status < 500) throw e;
      }
      await d.sleep(POLL_MS);
    }
    return "please_wait";
  }

  /** On unmount: stops reporting state and releases everything. */
  dispose(): void {
    this.disposed = true;
    void this.uploader?.stop();
    this.cleanup();
  }

  /** Releases the camera, overlay and encoder. Safe to call more than once. */
  cleanup(): void {
    this.overlay?.dispose();
    this.overlay = null;
    this.grabber?.close(); // close() stops it too
    this.grabber = null;
    if (this.cam) this.deps.stopCamera(this.cam, this.opts.video);
    this.cam = null;
    if (typeof document !== "undefined" && document.fullscreenElement) document.exitFullscreen?.().catch(() => undefined);
  }
}
