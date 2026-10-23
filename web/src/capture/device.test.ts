import { describe, expect, it, vi } from "vitest";
import { startTap, type DeviceEnv } from "./device";

const UA = {
  android:
    "Mozilla/5.0 (Linux; Android 14; SM-A145F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Mobile Safari/537.36",
  iphone:
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
  desktop:
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
};

function sentinel() {
  const s = { released: false, release: vi.fn(async () => void (s.released = true)) };
  return s;
}

function fakeEnv(ua: string, opts: { wakeLock?: boolean; fullscreenFails?: boolean; throwSync?: boolean } = {}) {
  const listeners = new Map<string, () => void>();
  const sentinels: ReturnType<typeof sentinel>[] = [];
  const doc = {
    fullscreenElement: null as Element | null,
    visibilityState: "visible" as DocumentVisibilityState,
    documentElement: {
      requestFullscreen: vi.fn(() => {
        if (opts.throwSync) throw new Error("sync boom");
        if (opts.fullscreenFails) return Promise.reject(new Error("denied"));
        doc.fullscreenElement = doc.documentElement as unknown as Element;
        return Promise.resolve();
      }),
    },
    exitFullscreen: vi.fn(async () => void (doc.fullscreenElement = null)),
    addEventListener: vi.fn((t: string, cb: () => void) => void listeners.set(t, cb)),
    removeEventListener: vi.fn((t: string) => void listeners.delete(t)),
  };
  const wakeLock = {
    request: vi.fn(async () => {
      if (opts.throwSync) throw new Error("wake boom");
      const s = sentinel();
      sentinels.push(s);
      return s;
    }),
  };
  const orientation = { lock: vi.fn(async () => undefined) };
  const motion = { requestPermission: vi.fn(async () => "granted" as const) };
  const env = {
    ua,
    maxTouchPoints: ua === UA.desktop ? 0 : 5,
    doc,
    wakeLock: opts.wakeLock === false ? undefined : wakeLock,
    orientation,
    motion,
  } as unknown as DeviceEnv;
  return { env, doc, wakeLock, orientation, motion, listeners, sentinels };
}

describe("startTap", () => {
  it("Android: asks for fullscreen and the wake lock synchronously, then locks portrait", async () => {
    const f = fakeEnv(UA.android);
    const dev = startTap(f.env);
    // Before any await: the gesture is still live.
    expect(f.doc.documentElement.requestFullscreen).toHaveBeenCalledTimes(1);
    expect(f.wakeLock.request).toHaveBeenCalledWith("screen");
    expect(f.motion.requestPermission).not.toHaveBeenCalled();
    await expect(dev.ready).resolves.toEqual({
      fullscreen: true, orientationLocked: true, wakeLock: true, motionPermission: "not-needed",
    });
    expect(f.orientation.lock).toHaveBeenCalledWith("portrait");
    dev.release();
  });

  it("iOS: no fullscreen, asks for motion permission synchronously", async () => {
    const f = fakeEnv(UA.iphone);
    const dev = startTap(f.env);
    expect(f.motion.requestPermission).toHaveBeenCalledTimes(1);
    expect(f.doc.documentElement.requestFullscreen).not.toHaveBeenCalled();
    const r = await dev.ready;
    expect(r).toMatchObject({ fullscreen: false, motionPermission: "granted" });
    dev.release();
  });

  it("desktop: leaves fullscreen to the session and never asks for motion", async () => {
    const f = fakeEnv(UA.desktop);
    const dev = startTap(f.env);
    expect(f.doc.documentElement.requestFullscreen).not.toHaveBeenCalled();
    expect(f.motion.requestPermission).not.toHaveBeenCalled();
    expect(await dev.ready).toMatchObject({ fullscreen: false, wakeLock: true, motionPermission: "not-needed" });
    dev.release();
  });

  it("asks for the wake lock only where it exists", async () => {
    const f = fakeEnv(UA.iphone, { wakeLock: false });
    const dev = startTap(f.env);
    expect(await dev.ready).toMatchObject({ wakeLock: false });
    expect(f.doc.addEventListener).not.toHaveBeenCalled();
    dev.release();
  });

  it("never throws when every request fails", async () => {
    const f = fakeEnv(UA.android, { throwSync: true });
    let dev!: ReturnType<typeof startTap>;
    expect(() => (dev = startTap(f.env))).not.toThrow();
    expect(await dev.ready).toMatchObject({ fullscreen: false, orientationLocked: false, wakeLock: false });
    expect(() => dev.release()).not.toThrow();

    const g = fakeEnv(UA.android, { fullscreenFails: true });
    const r = await startTap(g.env).ready;
    expect(r).toMatchObject({ fullscreen: false, orientationLocked: false, wakeLock: true });
    expect(g.orientation.lock).not.toHaveBeenCalled();
  });

  it("re-acquires the wake lock when the page is visible again after a release", async () => {
    const f = fakeEnv(UA.android);
    const dev = startTap(f.env);
    await dev.ready;
    f.sentinels[0]!.released = true; // the browser dropped it when the page was hidden
    f.listeners.get("visibilitychange")!();
    await Promise.resolve();
    expect(f.wakeLock.request).toHaveBeenCalledTimes(2);
    dev.release();
  });

  it("release() drops the wake lock, stops listening and leaves fullscreen", async () => {
    const f = fakeEnv(UA.android);
    const dev = startTap(f.env);
    await dev.ready;
    dev.release();
    dev.release();
    expect(f.sentinels[0]!.release).toHaveBeenCalledTimes(1);
    expect(f.doc.removeEventListener).toHaveBeenCalledWith("visibilitychange", expect.any(Function));
    expect(f.doc.exitFullscreen).toHaveBeenCalledTimes(1);
    expect(f.doc.fullscreenElement).toBeNull();
  });

  it("release() before the requests answer still cleans up when they do", async () => {
    const f = fakeEnv(UA.android);
    const dev = startTap(f.env);
    dev.release();
    await dev.ready;
    expect(f.sentinels[0]!.release).toHaveBeenCalled();
    expect(f.doc.exitFullscreen).toHaveBeenCalledTimes(1);
  });
});
