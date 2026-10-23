import { describe, expect, it, vi } from "vitest";
import { supportsResizeMode } from "./env";
import { runProbe, type ProbeDeps } from "./probe";

const SAFARI =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15";
const WORKING: MediaTrackConstraints = { width: { ideal: 640 }, height: { ideal: 480 }, frameRate: { ideal: 30 } };

/**
 * A camera simulated in virtual time: a frame every 33 ms; a switch to a supported mode takes `switchMs`, during which
 * no frames arrive; unsupported modes throw OverconstrainedError.
 */
function camera(opts: { supported: [number, number][]; switchMs?: number; resizeMode?: boolean }) {
  let clock = 0;
  let size: [number, number] = [640, 480];
  let pending: { size: [number, number]; at: number } | null = null;
  const applied: MediaTrackConstraints[] = [];
  const track = {
    getSettings: () => ({ width: size[0], height: size[1], frameRate: 30 }),
    getConstraints: () => WORKING,
    applyConstraints: vi.fn(async (c: MediaTrackConstraints) => {
      applied.push(c);
      const w = (c.width as ConstrainULongRange | undefined)?.exact;
      const h = (c.height as ConstrainULongRange | undefined)?.exact;
      if (w === undefined || h === undefined) return; // the restore
      if (!opts.supported.some(([a, b]) => a === w && b === h)) {
        throw Object.assign(new Error("Cannot satisfy constraints"), { name: "OverconstrainedError" });
      }
      clock += 5;
      pending = { size: [w, h], at: clock + (opts.switchMs ?? 250) };
    }),
  } as unknown as MediaStreamTrack;
  const deps: Partial<ProbeDeps> = {
    videoSize: () => size,
    nextFrame: async (timeoutMs) => {
      if (timeoutMs <= 0) return null;
      clock = pending ? Math.max(clock + 33, pending.at) : clock + 33; // frames lost while the sensor reconfigures
      if (pending && clock >= pending.at) {
        size = pending.size;
        pending = null;
      }
      return clock;
    },
    now: () => clock,
    sleep: async (ms) => {
      clock += ms;
    },
    resizeModeSupported: opts.resizeMode ?? true,
  };
  return { track, deps, applied };
}

const video = {} as HTMLVideoElement;
const REAL: [number, number][] = [[1280, 720], [640, 480]];

describe("runProbe", () => {
  it("an accepted mode records delivered and switch_ms; a refused one is data, not an error", async () => {
    const { track, deps, applied } = camera({ supported: REAL, switchMs: 250 });
    const rows = await runProbe(track, video, deps);
    expect(rows.map((r) => r.requested)).toEqual([[1280, 720, 30], [640, 480, 30], [1000, 750, 24]]);
    expect(rows[0]).toMatchObject({ accepted: true, delivered: [1280, 720] });
    expect(rows[0]!.switch_ms).toBeGreaterThanOrEqual(250);
    expect(rows[0]!.frames_missing).toBeGreaterThan(0);
    expect(rows[2]).toEqual({
      requested: [1000, 750, 24], accepted: false, delivered: null, switch_ms: null, frames_missing: null,
    });
    expect(applied.at(-1)).toEqual(WORKING); // working constraints restored
  });

  it("a virtual camera switches instantly to anything without losing frames", async () => {
    const { track, deps } = camera({ supported: [...REAL, [1000, 750]], switchMs: 0 });
    const rows = await runProbe(track, video, deps);
    expect(rows.every((r) => r.accepted)).toBe(true);
    expect(rows[2]!.delivered).toEqual([1000, 750]);
    expect(rows.map((r) => r.frames_missing)).toEqual([0, 0, 0]);
  });

  it("Safari skips the unusual mode", async () => {
    const { track, deps, applied } = camera({ supported: REAL, resizeMode: supportsResizeMode(SAFARI, { resizeMode: true }) });
    const rows = await runProbe(track, video, deps);
    expect(rows[2]).toEqual({
      requested: [1000, 750, 24], accepted: false, delivered: null, switch_ms: null, frames_missing: null,
    });
    expect(applied).toHaveLength(3); // two modes and the restore, nothing for the skipped one
  });
});
