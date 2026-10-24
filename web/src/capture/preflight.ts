// Quality preflight (CONTRACT §3 `Preflight`): about 3 s of fps, drops, blur, brightness and one face check,
// then the camera controls, the gyro and the mode probe. Never throws for poor capture: it only reports.
import type { ModeProbe, Preflight } from "../contracts";
import type { OpenCamera } from "./camera";
import { now } from "./clock";
import { detectGyro, parseUserAgent, platformOf } from "./env";
import { createFaceTracker, type FaceTracker } from "./face";
import { runProbe } from "./probe";
import { videoQualitySampler } from "./quality";
import { frameTime, median, sleep as realSleep, type FrameClock } from "./util";

export type { FrameClock } from "./util";

/** The slice of Y1's FrameGrabber the preflight needs. */
export interface FrameStatsSource {
  start(): void;
  stop(): void;
  stats(): { frames: number; medianFps: number; droppedRatio: number; clock: FrameClock };
}

export interface PreflightDeps {
  grabber?: FrameStatsSource;
  faceTracker?: () => Promise<FaceTracker>;
  sample?: () => { blur: number; brightness: number } | null;
  gyro?: () => Promise<boolean>;
  probe?: (track: MediaStreamTrack, video: HTMLVideoElement) => Promise<ModeProbe[]>;
  sleep?: (ms: number) => Promise<void>;
}

export const PREFLIGHT_MS = 3000;
export const SAMPLE_EVERY_MS = 200;
/** getCapabilities() keys that describe the stream, not a camera control. */
const NOT_CONTROLS = new Set(["deviceId", "groupId", "width", "height", "aspectRatio", "frameRate", "facingMode", "resizeMode"]);

/** Counts decoded frames with requestVideoFrameCallback (else rAF polling) to measure fps and dropped frames. */
export function videoFrameStats(video: HTMLVideoElement): FrameStatsSource {
  const times: number[] = [];
  let clock: FrameClock = "now";
  let firstPresented: number | null = null;
  let lastPresented = 0;
  let running = false;
  let lastMediaTime = -1;
  const onFrame = (t: number, m: VideoFrameCallbackMetadata) => {
    if (!running) return;
    const ft = frameTime(m, t);
    clock = ft.clock;
    times.push(ft.t);
    firstPresented ??= m.presentedFrames;
    lastPresented = m.presentedFrames;
    video.requestVideoFrameCallback(onFrame);
  };
  const poll = () => {
    if (!running) return;
    if (video.currentTime !== lastMediaTime) {
      lastMediaTime = video.currentTime;
      times.push(now());
    }
    requestAnimationFrame(poll);
  };
  return {
    start() {
      running = true;
      if (typeof video.requestVideoFrameCallback === "function") video.requestVideoFrameCallback(onFrame);
      else requestAnimationFrame(poll);
    },
    stop() {
      running = false;
    },
    stats() {
      const gaps = times.slice(1).map((t, k) => t - times[k]!).filter((g) => g > 0);
      const span = firstPresented === null ? 0 : lastPresented - firstPresented;
      return {
        frames: times.length,
        medianFps: gaps.length ? 1000 / median(gaps) : 0,
        droppedRatio: span > 0 ? Math.max(0, Math.min(1, 1 - (times.length - 1) / span)) : 0,
        clock,
      };
    },
  };
}

export async function runPreflight(
  video: HTMLVideoElement, cam: OpenCamera, opts: { noFlashRequested: boolean }, deps: PreflightDeps = {},
): Promise<Preflight> {
  const grabber = deps.grabber ?? videoFrameStats(video);
  const sample = deps.sample ?? videoQualitySampler(video);
  const sleep = deps.sleep ?? realSleep;
  const tracker = (deps.faceTracker ?? createFaceTracker)().catch(() => null); // loads while we measure
  const gyro = (deps.gyro ?? detectGyro)().catch(() => false);

  const blurs: number[] = [];
  const lumas: number[] = [];
  grabber.start();
  for (let k = 0; k < PREFLIGHT_MS / SAMPLE_EVERY_MS; k++) {
    const q = sample();
    if (q) {
      blurs.push(q.blur);
      lumas.push(q.brightness);
    }
    await sleep(SAMPLE_EVERY_MS);
  }
  grabber.stop();
  const stats = grabber.stats();

  const face = (await tracker)?.detect(video, now()) ?? { found: false, box: null, yawDeg: null };
  const width = video.videoWidth || cam.settings.width || 0;
  const height = video.videoHeight || cam.settings.height || 0;
  const caps = (cam.track.getCapabilities?.() ?? {}) as Record<string, unknown>;
  const ua = navigator.userAgent;
  const probe = await (deps.probe ?? runProbe)(cam.track, video).catch(() => []);

  return {
    user_agent: ua,
    platform: platformOf(ua, navigator.maxTouchPoints ?? 0),
    browser: parseUserAgent(ua).browser,
    camera_label: cam.track.label ?? "",
    width,
    height,
    measured_fps: stats.medianFps,
    dropped_frame_ratio: stats.droppedRatio,
    blur: median(blurs),
    brightness: median(lumas),
    face_found: face.found,
    face_fraction: face.found && face.box ? face.box[2] * face.box[3] : 0,
    controls: Object.keys(caps).filter((k) => !NOT_CONTROLS.has(k)),
    gyro: await gyro,
    no_flash_requested: opts.noFlashRequested,
    clock: stats.clock,
    probe,
  };
}
