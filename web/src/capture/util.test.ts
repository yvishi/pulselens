import { describe, expect, it, vi } from "vitest";
import { frameTime, median, nextFrame, sleep } from "./util";

describe("frameTime", () => {
  it("prefers captureTime", () => {
    expect(frameTime({ captureTime: 1000, expectedDisplayTime: 1050 }, 1100)).toEqual({ t: 1000, clock: "captureTime" });
  });

  it("falls back to expectedDisplayTime", () => {
    expect(frameTime({ expectedDisplayTime: 1050 }, 1100)).toEqual({ t: 1050, clock: "expectedDisplayTime" });
  });

  it("falls back to the callback time", () => {
    expect(frameTime({}, 1100)).toEqual({ t: 1100, clock: "now" });
  });

  it("treats a zero captureTime as present", () => {
    expect(frameTime({ captureTime: 0, expectedDisplayTime: 5 }, 9)).toEqual({ t: 0, clock: "captureTime" });
  });
});

describe("median", () => {
  it("handles odd, even and empty lists without mutating the input", () => {
    const xs = [4, 1, 3, 2];
    expect(median([3, 1, 2])).toBe(2);
    expect(median(xs)).toBe(2.5);
    expect(xs).toEqual([4, 1, 3, 2]);
    expect(median([])).toBe(0);
  });
});

describe("sleep and nextFrame", () => {
  it("sleep resolves after the delay, and at once for a negative one", async () => {
    vi.useFakeTimers();
    try {
      let done = false;
      void sleep(50).then(() => (done = true));
      await vi.advanceTimersByTimeAsync(49);
      expect(done).toBe(false);
      await vi.advanceTimersByTimeAsync(1);
      expect(done).toBe(true);
      let neg = false;
      void sleep(-10).then(() => (neg = true));
      await vi.advanceTimersByTimeAsync(0);
      expect(neg).toBe(true);
    } finally {
      vi.useRealTimers();
    }
  });

  it("nextFrame resolves on the next animation frame", async () => {
    const raf = vi.fn((cb: FrameRequestCallback) => (cb(0), 1));
    vi.stubGlobal("requestAnimationFrame", raf);
    try {
      await nextFrame();
      expect(raf).toHaveBeenCalledTimes(1);
    } finally {
      vi.unstubAllGlobals();
    }
  });
});
