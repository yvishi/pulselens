import { describe, expect, it, vi } from "vitest";
import type { OpenCamera } from "./camera";
import { runPreflight, type PreflightDeps } from "./preflight";

function setup() {
  const track = {
    label: "Integrated Webcam",
    getCapabilities: () => ({ deviceId: "x", width: { max: 1280 }, exposureMode: ["manual"], torch: true }),
    getSettings: () => ({ width: 640, height: 480, frameRate: 30 }),
  } as unknown as MediaStreamTrack;
  const cam = { stream: {} as MediaStream, track, settings: track.getSettings() } as OpenCamera;
  const video = { videoWidth: 640, videoHeight: 480 } as HTMLVideoElement;
  const grabber = {
    start: vi.fn(),
    stop: vi.fn(),
    stats: () => ({ frames: 90, medianFps: 29.8, droppedRatio: 0.02, clock: "captureTime" as const }),
  };
  const sample = vi.fn().mockReturnValueOnce({ blur: 50, brightness: 120 }).mockReturnValue({ blur: 40, brightness: 110 });
  const deps: PreflightDeps = {
    grabber,
    faceTracker: async () => ({ detect: () => ({ found: true, box: [0.25, 0.2, 0.5, 0.6], yawDeg: 3 }) }),
    sample,
    gyro: async () => true,
    probe: async () => [{ requested: [1280, 720, 30], accepted: true, delivered: [1280, 720], switch_ms: 300, frames_missing: 6 }],
    sleep: async () => undefined,
  };
  return { cam, video, grabber, sample, deps };
}

describe("runPreflight", () => {
  it("returns every Preflight field with the right types", async () => {
    const { cam, video, grabber, sample, deps } = setup();
    const p = await runPreflight(video, cam, { noFlashRequested: true }, deps);
    expect(Object.keys(p).sort()).toEqual([
      "blur", "brightness", "browser", "camera_label", "clock", "controls", "dropped_frame_ratio", "face_found",
      "face_fraction", "gyro", "height", "measured_fps", "no_flash_requested", "platform", "probe", "user_agent", "width",
    ]);
    for (const k of ["user_agent", "platform", "browser", "camera_label", "clock"] as const) expect(typeof p[k]).toBe("string");
    for (const k of ["width", "height", "measured_fps", "dropped_frame_ratio", "blur", "brightness", "face_fraction"] as const) {
      expect(Number.isFinite(p[k])).toBe(true);
    }
    expect(p).toMatchObject({
      camera_label: "Integrated Webcam", width: 640, height: 480, measured_fps: 29.8, dropped_frame_ratio: 0.02,
      blur: 40, brightness: 110, face_found: true, gyro: true, no_flash_requested: true, clock: "captureTime",
      controls: ["exposureMode", "torch"],
    });
    expect(p.face_fraction).toBeCloseTo(0.3);
    expect(p.probe).toHaveLength(1);
    expect(grabber.start).toHaveBeenCalledOnce();
    expect(grabber.stop).toHaveBeenCalledOnce();
    expect(sample.mock.calls.length).toBeGreaterThanOrEqual(10); // every 200 ms over >= 2 s
  });

  it("abstains softly when the face model or the gyro fails", async () => {
    const { cam, video, deps } = setup();
    deps.faceTracker = async () => {
      throw new Error("no model");
    };
    deps.gyro = async () => {
      throw new Error("denied");
    };
    deps.sample = () => null;
    const p = await runPreflight(video, cam, { noFlashRequested: false }, deps);
    expect(p).toMatchObject({ face_found: false, face_fraction: 0, gyro: false, blur: 0, brightness: 0 });
  });
});
