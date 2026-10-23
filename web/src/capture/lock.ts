/**
 * Exposure lock for the light challenge: an EXPERIMENT behind `?lock=1` (cut-list item 6). Auto exposure lengthens
 * frames in a dim room (a USB webcam fell from 30 to 10.4 fps) and auto white balance can chase the colours and
 * cancel part of the echo. Where the camera offers manual modes, both are frozen for the colour steps and handed
 * back afterwards. Unconfirmed on real hardware (docs/REFERENCE.md).
 */
import type { Preflight } from "../contracts";

/** Whether to try the lock: the `?lock=1` flag, a slow camera (fps < 27) and an exposureMode control. */
export function shouldLock(pf: Pick<Preflight, "measured_fps" | "controls">, search = location.search): boolean {
  return new URLSearchParams(search).get("lock") === "1" && pf.measured_fps < LOCK_BELOW_FPS
    && pf.controls.includes("exposureMode");
}

export type CameraLock = {
  exposure: boolean;
  white_balance: boolean;
  /** applied exposureTime, in the constraint's units (100 µs) */
  exposure_time: number | null;
  error: string | null;
};

/** 33.3 ms: the longest exposure that still allows 30 fps, in exposureTime units of 100 µs. */
export const MAX_EXPOSURE_TIME = 333;
/** Below this measured frame rate auto exposure is stretching frames, so exposure gets locked. */
export const LOCK_BELOW_FPS = 27;

type Range = { min?: number; max?: number };
type Caps = { exposureMode?: string[]; exposureTime?: Range; whiteBalanceMode?: string[]; colorTemperature?: Range };
type Settings = { exposureTime?: number; colorTemperature?: number };

const clamp = (x: number, r: Range | undefined) => Math.min(r?.max ?? x, Math.max(r?.min ?? x, x));

/**
 * The constraint set that freezes white balance and, only when auto exposure is slowing the camera (measured fps
 * below 27), exposure at 33 ms; null when nothing applies. The exposureTime a camera reports in continuous mode is
 * not trusted: at G1 it said 15.6 ms while frames came every 96 ms, and locking at 15.6 ms made the face 10x darker.
 */
export function lockConstraints(
  caps: Caps,
  settings: Settings,
  fps: number | null,
): { set: MediaTrackConstraintSet; lock: CameraLock } | null {
  const set: Record<string, unknown> = {};
  const lock: CameraLock = { exposure: false, white_balance: false, exposure_time: null, error: null };
  if (caps.exposureMode?.includes("manual") && caps.exposureTime && fps !== null && fps < LOCK_BELOW_FPS) {
    const t = clamp(MAX_EXPOSURE_TIME, caps.exposureTime);
    Object.assign(set, { exposureMode: "manual", exposureTime: t });
    Object.assign(lock, { exposure: true, exposure_time: t });
  }
  if (caps.whiteBalanceMode?.includes("manual") && caps.colorTemperature && settings.colorTemperature) {
    Object.assign(set, { whiteBalanceMode: "manual", colorTemperature: clamp(settings.colorTemperature, caps.colorTemperature) });
    lock.white_balance = true;
  }
  return lock.exposure || lock.white_balance ? { set: set as MediaTrackConstraintSet, lock } : null;
}

/** Freezes the camera for the light suite; returns what was locked and a restore function (never throws). */
export async function lockForLight(
  track: MediaStreamTrack,
  fps: number | null,
): Promise<{ lock: CameraLock | null; restore: () => Promise<void> }> {
  const none = { lock: null, restore: async () => undefined };
  let plan: ReturnType<typeof lockConstraints>;
  try {
    plan = lockConstraints((track.getCapabilities?.() ?? {}) as Caps, (track.getSettings?.() ?? {}) as Settings, fps);
  } catch {
    return none; // getCapabilities throws on some browsers (Firefox)
  }
  if (!plan) return none;
  try {
    await track.applyConstraints({ advanced: [plan.set] });
  } catch (e) {
    return { lock: { ...plan.lock, exposure: false, white_balance: false, error: String(e) }, restore: none.restore };
  }
  const back: Record<string, string> = {};
  if (plan.lock.exposure) back.exposureMode = "continuous";
  if (plan.lock.white_balance) back.whiteBalanceMode = "continuous";
  return {
    lock: plan.lock,
    restore: async () => {
      await track.applyConstraints({ advanced: [back as MediaTrackConstraintSet] }).catch(() => undefined);
    },
  };
}
