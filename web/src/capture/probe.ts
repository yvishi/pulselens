// Mode-switch probe (CONTRACT §3 `ModeProbe`): ask the camera for exact modes and time how it really switches.
// A real sensor refuses odd modes or reconfigures slowly and loses frames; a virtual camera rescales anything at once.
import type { ModeProbe } from "../contracts";
import { now } from "./clock";
import { supportsResizeMode } from "./env";
import { frameTime, sleep } from "./util";

export const PROBE_MODES: [number, number, number][] = [[1280, 720, 30], [640, 480, 30], [1000, 750, 24]];
/** Index of the unusual mode real webcams rarely offer. */
const UNUSUAL = 2;

export interface ProbeDeps {
  /** current decoded size of the video */
  videoSize: () => [number, number];
  /** time of the next decoded frame (performance.now() domain), or null after `timeoutMs` */
  nextFrame: (timeoutMs: number) => Promise<number | null>;
  now: () => number;
  sleep: (ms: number) => Promise<void>;
  resizeModeSupported: boolean;
  settleMs: number;
}

/** Resolves with the next video frame time, or null after `timeoutMs` (rVFC, else rAF polling of currentTime). */
export function nextVideoFrame(video: HTMLVideoElement, timeoutMs: number): Promise<number | null> {
  return new Promise((resolve) => {
    let done = false;
    const finish = (t: number | null) => {
      if (done) return;
      done = true;
      clearTimeout(timer);
      resolve(t);
    };
    const timer = setTimeout(() => finish(null), Math.max(0, timeoutMs));
    if (typeof video.requestVideoFrameCallback === "function") {
      video.requestVideoFrameCallback((t, m) => finish(frameTime(m, t).t));
    } else {
      const start = video.currentTime;
      const poll = () => {
        if (done) return;
        if (video.currentTime !== start) finish(now());
        else requestAnimationFrame(poll);
      };
      requestAnimationFrame(poll);
    }
  });
}

const skipped = (requested: [number, number, number]): ModeProbe =>
  ({ requested, accepted: false, delivered: null, switch_ms: null, frames_missing: null });

/**
 * Tries each of PROBE_MODES with exact size and resizeMode "none", waits up to 1000 ms for a frame at the new size,
 * then restores the working constraints. A refusal (OverconstrainedError) is data: accepted=false.
 */
export async function runProbe(
  track: MediaStreamTrack, video: HTMLVideoElement, deps: Partial<ProbeDeps> = {},
): Promise<ModeProbe[]> {
  const d: ProbeDeps = {
    videoSize: () => [video.videoWidth, video.videoHeight],
    nextFrame: (ms) => nextVideoFrame(video, ms),
    now,
    sleep,
    resizeModeSupported: supportsResizeMode(),
    settleMs: 1000,
    ...deps,
  };
  const working = track.getConstraints?.() ?? {};
  const rows: ModeProbe[] = [];
  for (const [k, requested] of PROBE_MODES.entries()) {
    const [width, height, frameRate] = requested;
    if (k === UNUSUAL && !d.resizeModeSupported) {
      rows.push(skipped(requested));
      continue;
    }
    await d.nextFrame(d.settleMs); // start on a frame boundary
    const oldFps = track.getSettings?.().frameRate || 30;
    const start = d.now();
    try {
      await track.applyConstraints({
        width: { exact: width }, height: { exact: height }, frameRate: { ideal: frameRate }, resizeMode: "none",
      } as MediaTrackConstraints);
    } catch {
      rows.push(skipped(requested));
      continue;
    }
    const deadline = start + d.settleMs;
    let frames = 0;
    let matchT: number | null = null;
    while (d.now() < deadline) {
      const t = await d.nextFrame(deadline - d.now());
      if (t === null) break;
      frames++;
      const [w, h] = d.videoSize();
      if (w === width && h === height) {
        matchT = t;
        break;
      }
    }
    const switchMs = matchT === null ? null : matchT - start;
    rows.push({
      requested,
      accepted: true,
      delivered: d.videoSize(),
      switch_ms: switchMs,
      frames_missing: switchMs === null ? null : Math.max(0, Math.round((switchMs * oldFps) / 1000) - frames),
    });
    await d.sleep(Math.max(0, deadline - d.now())); // let the camera settle before the next request
  }
  await track.applyConstraints(working).catch(() => undefined);
  return rows;
}
