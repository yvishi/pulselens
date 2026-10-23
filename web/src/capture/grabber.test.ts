import { describe, expect, it, vi } from "vitest";
import type { FrameEncoder } from "./encoder";
import { fitSize, FrameGrabber, type GrabbedFrame } from "./grabber";

type Md = { captureTime?: number; expectedDisplayTime?: number; presentedFrames?: number };
type Cb = (now: number, md: Md) => void;

/** A video element whose requestVideoFrameCallback the test fires by hand. */
function fakeVideo(w = 640, h = 480) {
  let pending: Cb | null = null;
  const video = document.createElement("video");
  Object.defineProperty(video, "videoWidth", { value: w });
  Object.defineProperty(video, "videoHeight", { value: h });
  (video as unknown as { requestVideoFrameCallback: (cb: Cb) => number }).requestVideoFrameCallback = (cb) => {
    pending = cb;
    return 1;
  };
  const fire = (now: number, md: Md) => {
    const cb = pending;
    pending = null;
    cb?.(now, md);
  };
  return { video, fire };
}

function grabber(video: HTMLVideoElement, t0 = 0, clock?: () => number) {
  const frames: GrabbedFrame[] = [];
  const encode = vi.fn<FrameEncoder["encode"]>(async () => new Blob(["x"], { type: "image/jpeg" }));
  const g = new FrameGrabber(video, {
    size: [640, 480], jpegQuality: 0.9, t0, onFrame: (f) => frames.push(f), encoder: { encode, close: vi.fn() },
    now: clock,
  });
  return { g, frames, encode };
}

const flush = () => new Promise((r) => setTimeout(r, 0));

describe("fitSize", () => {
  it("keeps aspect: fits inside the box in the frame's own orientation and never upscales", () => {
    expect(fitSize(1280, 720, [640, 480])).toEqual([640, 360]);
    expect(fitSize(720, 1280, [640, 480])).toEqual([360, 640]);
    expect(fitSize(1920, 1080, [480, 360])).toEqual([480, 270]);
    expect(fitSize(320, 240, [640, 480])).toEqual([320, 240]);
    expect(fitSize(0, 0, [640, 480])).toEqual([1, 1]);
  });
});

describe("FrameGrabber (rVFC)", () => {
  it("uses captureTime when present: t_ms = captureTime - t0", async () => {
    const { video, fire } = fakeVideo(1280, 720);
    const { g, frames, encode } = grabber(video, 900);
    g.start();
    fire(1100, { captureTime: 1000, expectedDisplayTime: 1050, presentedFrames: 1 });
    fire(1133, { captureTime: 1033, expectedDisplayTime: 1083, presentedFrames: 2 });
    await flush();
    expect(frames.map((f) => f.t_ms)).toEqual([100, 133]);
    expect(frames.map((f) => [f.w, f.h])).toEqual([[640, 360], [640, 360]]);
    expect(encode).toHaveBeenCalledWith(video, 640, 360, 0.9);
    expect(g.stats().clock).toBe("captureTime");
  });

  it("falls back to expectedDisplayTime, then the callback time", async () => {
    const { video, fire } = fakeVideo();
    const { g, frames } = grabber(video, 100);
    g.start();
    fire(500, { expectedDisplayTime: 480, presentedFrames: 1 });
    expect(g.stats().clock).toBe("expectedDisplayTime");
    fire(540, { presentedFrames: 2 });
    expect(g.stats().clock).toBe("now");
    await flush();
    expect(frames.map((f) => f.t_ms)).toEqual([380, 440]);
  });

  it("idx strictly increasing, skipping frames whose time does not move forward", async () => {
    const { video, fire } = fakeVideo();
    const { g, frames } = grabber(video);
    g.start();
    for (const [now, ct] of [[100, 50], [140, 50], [150, 40], [180, 83], [210, 116]] as const)
      fire(now, { captureTime: ct, presentedFrames: 0 });
    await flush();
    expect(frames.map((f) => f.t_ms)).toEqual([50, 83, 116]);
    const idx = frames.map((f) => f.idx);
    expect(idx[0]).toBe(0);
    for (let k = 1; k < idx.length; k++) expect(idx[k]).toBeGreaterThan(idx[k - 1]!);
  });

  it("medianFps from intervals: 33.3 ms -> 30 fps", () => {
    const { video, fire } = fakeVideo();
    const { g } = grabber(video);
    g.start();
    expect(g.stats().medianFps).toBe(0);
    for (let k = 0; k < 60; k++) fire(0, { captureTime: 1000 + 33.3 * k, presentedFrames: k + 1 });
    const s = g.stats();
    expect(s.frames).toBe(60);
    expect(Math.abs(s.medianFps - 30)).toBeLessThan(0.5);
    expect(s.droppedRatio).toBe(0);
  });

  it("droppedRatio from presentedFrames gaps", () => {
    const { video, fire } = fakeVideo();
    const { g } = grabber(video);
    g.start();
    // presented 1, 2, 4, 5, 8: frames 3, 6, 7 never reached the callback -> 3 dropped of 8.
    [1, 2, 4, 5, 8].forEach((p, k) => fire(0, { captureTime: 33 * (k + 1), presentedFrames: p }));
    expect(g.stats().droppedRatio).toBeCloseTo(3 / 8, 6);
  });

  it("stops asking for frames after stop()", async () => {
    const { video, fire } = fakeVideo();
    const { g, frames } = grabber(video);
    g.start();
    fire(10, { captureTime: 10, presentedFrames: 1 });
    g.stop();
    fire(43, { captureTime: 43, presentedFrames: 2 });
    await flush();
    expect(frames).toHaveLength(1);
  });

  it("does not emit frames before the video has a size, and drops frames that fail to encode", async () => {
    const { video, fire } = fakeVideo(0, 0);
    const { g, frames } = grabber(video);
    g.start();
    fire(10, { captureTime: 10, presentedFrames: 1 });
    await flush();
    expect(frames).toHaveLength(0);

    const v2 = fakeVideo();
    const { g: g2, frames: f2, encode } = grabber(v2.video);
    encode.mockRejectedValueOnce(new Error("boom"));
    g2.start();
    v2.fire(10, { captureTime: 10, presentedFrames: 1 });
    v2.fire(43, { captureTime: 43, presentedFrames: 2 });
    await flush();
    expect(f2.map((f) => f.idx)).toEqual([1]);
  });

  it("fpsOver(ms): null until the grabber has run for ms, then frames in the last ms per second", () => {
    let t = 1000;
    const { video, fire } = fakeVideo();
    const { g } = grabber(video, 0, () => t);
    g.start(); // started at 1000
    for (let k = 0; k < 30; k++) fire(0, { captureTime: 1000 + 33.3 * k, presentedFrames: k + 1 });
    t = 2000;
    expect(g.fpsOver(2000)).toBeNull();
    // 30 fps until 3000, then 5 fps until 5000
    for (let k = 30; k < 60; k++) fire(0, { captureTime: 1000 + 33.3 * k, presentedFrames: k + 1 });
    t = 3000;
    expect(g.fpsOver(2000)).toBeCloseTo(30, 0);
    for (let k = 1; k <= 10; k++) fire(0, { captureTime: 3000 + 200 * k, presentedFrames: 60 + k });
    t = 5000;
    expect(g.fpsOver(2000)).toBeCloseTo(5, 0);
    t = 7500; // a frozen stream: no frames at all in the window
    expect(g.fpsOver(2000)).toBe(0);
  });
});
