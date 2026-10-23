import { describe, expect, it, vi } from "vitest";
import { LOCK_BELOW_FPS, lockConstraints, lockForLight, MAX_EXPOSURE_TIME, shouldLock } from "./lock";

// The G1 webcam (USB2.0 HD UVC WebCam): manual exposure 2.4..5000 (100 µs units) and manual white balance.
const G1_CAPS = {
  exposureMode: ["continuous", "manual"],
  exposureTime: { min: 2.44140625, max: 5000 },
  whiteBalanceMode: ["continuous", "manual"],
  colorTemperature: { min: 2800, max: 6500 },
};

function fakeTrack(caps: object, settings: object, apply = vi.fn(async () => undefined)) {
  return { track: { getCapabilities: () => caps, getSettings: () => settings, applyConstraints: apply } as unknown as MediaStreamTrack, apply };
}

describe("lockConstraints", () => {
  it("at 10 fps locks exposure at 33 ms, ignoring the stale 15.6 ms the camera reports, and white balance", () => {
    const plan = lockConstraints(G1_CAPS, { exposureTime: 156.25, colorTemperature: 4600 }, 10.4)!;
    expect(plan.set).toEqual({ exposureMode: "manual", exposureTime: MAX_EXPOSURE_TIME, whiteBalanceMode: "manual", colorTemperature: 4600 });
    expect(plan.lock).toEqual({ exposure: true, white_balance: true, exposure_time: MAX_EXPOSURE_TIME, error: null });
  });

  it("leaves exposure alone when the camera already runs at full rate (bright room), locking only white balance", () => {
    const plan = lockConstraints(G1_CAPS, { colorTemperature: 4600 }, 30)!;
    expect(plan.lock).toMatchObject({ exposure: false, white_balance: true });
    expect(plan.set).not.toHaveProperty("exposureMode");
    expect(lockConstraints(G1_CAPS, {}, LOCK_BELOW_FPS)).toBeNull(); // no temperature to hold, no slowdown
  });

  it("does not lock exposure before the frame rate is known", () => {
    expect(lockConstraints(G1_CAPS, {}, null)).toBeNull();
  });

  it("stays inside the camera's range", () => {
    expect(lockConstraints({ ...G1_CAPS, exposureTime: { min: 1, max: 200 } }, {}, 10)!.lock.exposure_time).toBe(200);
  });

  it("locks nothing on cameras without manual modes", () => {
    expect(lockConstraints({ exposureMode: ["continuous"] }, { exposureTime: 100 }, 10)).toBeNull();
    expect(lockConstraints({}, {}, 10)).toBeNull(); // Safari and Firefox report no controls
  });
});

describe("lockForLight", () => {
  it("applies the lock, then restores continuous modes", async () => {
    const { track, apply } = fakeTrack(G1_CAPS, { exposureTime: 156.25, colorTemperature: 4600 });
    const { lock, restore } = await lockForLight(track, 10.4);
    expect(lock).toMatchObject({ exposure: true, white_balance: true });
    expect(apply).toHaveBeenLastCalledWith({ advanced: [expect.objectContaining({ exposureMode: "manual" })] });
    await restore();
    expect(apply).toHaveBeenLastCalledWith({ advanced: [{ exposureMode: "continuous", whiteBalanceMode: "continuous" }] });
  });

  it("reports a refused lock instead of throwing, and restores nothing", async () => {
    const apply = vi.fn(async () => Promise.reject(new DOMException("not supported", "OverconstrainedError")));
    const { track } = fakeTrack(G1_CAPS, { colorTemperature: 4600 }, apply);
    const { lock, restore } = await lockForLight(track, 10.4);
    expect(lock).toMatchObject({ exposure: false, white_balance: false });
    expect(lock!.error).toContain("not supported");
    await restore();
    expect(apply).toHaveBeenCalledTimes(1);
  });

  it("does nothing on a camera without getCapabilities", async () => {
    const track = { getSettings: () => ({}), applyConstraints: vi.fn() } as unknown as MediaStreamTrack;
    expect((await lockForLight(track, 10)).lock).toBeNull();
  });
});

describe("shouldLock", () => {
  const slow = { measured_fps: 10.4, controls: ["exposureMode", "whiteBalanceMode"] };
  it("needs the ?lock=1 flag, fps below 27 and an exposureMode control", () => {
    expect(shouldLock(slow, "?lock=1")).toBe(true);
    expect(shouldLock(slow, "")).toBe(false);
    expect(shouldLock(slow, "?lock=0")).toBe(false);
    expect(shouldLock({ ...slow, measured_fps: 30 }, "?lock=1")).toBe(false);
    expect(shouldLock({ ...slow, controls: [] }, "?lock=1")).toBe(false);
  });
});
