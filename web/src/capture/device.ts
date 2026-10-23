/**
 * Phone set-up on the Start tap (Y7). Browsers grant fullscreen, the iOS motion prompt and (on some) the wake lock
 * only while the user gesture is live, so startTap() asks for all of them synchronously, before the first await,
 * and returns a handle at once. Nothing here throws: a refusal only means the session runs without that feature.
 *
 * - Android: requestFullscreen() on <html>, then a portrait orientation lock once fullscreen is granted.
 * - iOS (iPhone, iPad, a touch Mac): no Fullscreen API, so the overlay covers the viewport instead (overlay.ts);
 *   DeviceMotionEvent.requestPermission() so the gyro check can see motion events.
 * - Desktop: nothing here; CaptureSession's chooseOverlayMode() asks for fullscreen itself (asking twice would make
 *   the second request fail and drop the overlay to the border fallback).
 * - Everywhere it exists: a screen wake lock, re-acquired when the page becomes visible again after a release.
 */
import { platformOf } from "./env";

type MotionAnswer = "granted" | "denied";
type MotionRequester = { requestPermission?: () => Promise<MotionAnswer> };
type LockableOrientation = { lock?: (o: string) => Promise<void> };
interface WakeLockLike {
  released: boolean;
  release(): Promise<void>;
  addEventListener?(type: "release", cb: () => void): void;
}

/** The browser surface startTap uses; injectable for tests. */
export interface DeviceEnv {
  ua: string;
  maxTouchPoints: number;
  doc: Pick<Document, "documentElement" | "fullscreenElement" | "exitFullscreen" | "visibilityState" | "addEventListener" | "removeEventListener">;
  wakeLock?: { request(type: "screen"): Promise<WakeLockLike> };
  orientation?: LockableOrientation;
  motion?: MotionRequester;
}

export function browserEnv(): DeviceEnv {
  const nav = navigator as Navigator & { wakeLock?: DeviceEnv["wakeLock"] };
  return {
    ua: nav.userAgent,
    maxTouchPoints: nav.maxTouchPoints ?? 0,
    doc: document,
    wakeLock: nav.wakeLock,
    orientation: (globalThis.screen?.orientation as LockableOrientation | undefined) ?? undefined,
    motion: (globalThis as unknown as { DeviceMotionEvent?: MotionRequester }).DeviceMotionEvent,
  };
}

export interface StartTapResult {
  fullscreen: boolean;
  orientationLocked: boolean;
  wakeLock: boolean;
  motionPermission: MotionAnswer | "not-needed";
}

export interface DeviceSession {
  /** settles once every request has answered; never rejects */
  ready: Promise<StartTapResult>;
  /** releases the wake lock, stops re-acquiring it and leaves fullscreen; safe to call more than once */
  release(): void;
}

/** Call straight from the Start click, before any await. */
export function startTap(env: DeviceEnv = browserEnv()): DeviceSession {
  const platform = platformOf(env.ua, env.maxTouchPoints);
  const doc = env.doc;
  const attempt = <T>(f: () => Promise<T> | undefined): Promise<T> | undefined => {
    try {
      return f();
    } catch (e) {
      return Promise.reject(e);
    }
  };

  // All three requests start here, synchronously, inside the gesture.
  const fullscreenReq =
    platform === "android" && typeof doc.documentElement.requestFullscreen === "function"
      ? attempt(() => doc.documentElement.requestFullscreen())
      : undefined;
  const motionReq =
    platform === "ios" && typeof env.motion?.requestPermission === "function"
      ? attempt(() => env.motion!.requestPermission!())
      : undefined;

  let released = false;
  let sentinel: WakeLockLike | null = null;
  let enteredFullscreen = false;
  const acquire = (): Promise<boolean> | undefined => {
    if (!env.wakeLock || released) return undefined;
    return (attempt(() => env.wakeLock!.request("screen")) ?? Promise.reject(new Error("no wake lock"))).then(
      (s) => {
        if (released) {
          void s.release().catch(() => undefined);
          return false;
        }
        sentinel = s;
        return true;
      },
      () => false,
    );
  };
  const wakeReq = acquire();
  // The browser drops the lock when the page is hidden; take it again when the customer comes back.
  const onVisible = () => {
    if (!released && doc.visibilityState === "visible" && (!sentinel || sentinel.released)) void acquire();
  };
  if (env.wakeLock) doc.addEventListener("visibilitychange", onVisible);

  const ready = (async (): Promise<StartTapResult> => {
    const result: StartTapResult = { fullscreen: false, orientationLocked: false, wakeLock: false, motionPermission: "not-needed" };
    if (fullscreenReq) {
      result.fullscreen = await fullscreenReq.then(() => true, () => false);
      enteredFullscreen = result.fullscreen;
      if (result.fullscreen && !released) {
        const lock = env.orientation?.lock;
        result.orientationLocked = lock
          ? await (attempt(() => lock.call(env.orientation, "portrait")) ?? Promise.reject()).then(() => true, () => false)
          : false;
      }
      if (released) exitFullscreen();
    }
    if (wakeReq) result.wakeLock = await wakeReq;
    if (motionReq) result.motionPermission = await motionReq.catch(() => "denied" as const);
    return result;
  })();

  function exitFullscreen(): void {
    if (!enteredFullscreen || !doc.fullscreenElement) return;
    enteredFullscreen = false;
    void attempt(() => doc.exitFullscreen())?.catch(() => undefined);
  }

  return {
    ready,
    release() {
      if (released) return;
      released = true;
      doc.removeEventListener("visibilitychange", onVisible);
      const s = sentinel;
      sentinel = null;
      if (s && !s.released) void attempt(() => s.release())?.catch(() => undefined);
      exitFullscreen();
    },
  };
}
