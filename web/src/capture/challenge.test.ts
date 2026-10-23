import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Challenge, ChallengeEvent, Step } from "../contracts";
import { isRedHue, runChallenge, type Overlay } from "./challenge";
import { now } from "./clock";

/** A fake overlay: each paint/clear lands one 16 ms frame later and is logged in ms since t0. */
function fakeOverlay() {
  const changes: number[] = [];
  const frame = () => new Promise<number>((r) => setTimeout(() => {
    const t = now() - overlay.t0;
    changes.push(t);
    r(t);
  }, 16));
  const overlay: Overlay & { changes: number[] } = { t0: 0, changes, paint: frame, clear: frame };
  return overlay;
}

const colour = (step_id: string, hue_deg: number, start_offset_ms: number, dwell_ms = 300): Step =>
  ({ kind: "colour", step_id, hue_deg, start_offset_ms, dwell_ms });

function challenge(steps: Step[], baseline_ms = 1000): Challenge {
  return { session_id: "s", nonce: "n", mode: "CAPABLE", baseline_ms, steps, total_ms: 10_000 };
}

async function run(ch: Challenge, skip: () => string | null = () => null, overlay = fakeOverlay()) {
  const t0 = now();
  const showTurnPrompt = vi.fn(async (_dir: "left" | "right", ms: number) => {
    const painted = now() - t0;
    await new Promise((r) => setTimeout(r, ms));
    return { painted, ended: now() - t0 };
  });
  const p = runChallenge(ch, { overlay, t0, showTurnPrompt, shouldSkipLight: skip });
  const settled: Promise<{ events?: ChallengeEvent[]; error?: unknown }> = p.then((events) => ({ events }), (error: unknown) => ({ error }));
  await vi.runAllTimersAsync();
  return { ...(await settled), overlay, showTurnPrompt };
}

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

describe("runChallenge", () => {
  const steps: Step[] = [
    colour("c0", 40, 0),
    colour("c1", 200, 1000),
    { kind: "turn", step_id: "t0", direction: "left", start_offset_ms: 2000, duration_ms: 1500 },
    colour("c2", 300, 4000),
  ];

  it("returns events in step order, each painted no earlier than scheduled", async () => {
    const { events, showTurnPrompt } = await run(challenge(steps));
    expect(events!.map((e) => e.step_id)).toEqual(["c0", "c1", "t0", "c2"]);
    events!.forEach((e, k) => {
      expect(e.status).toBe("shown");
      expect(e.painted_t_ms!).toBeGreaterThanOrEqual(1000 + steps[k]!.start_offset_ms);
      expect(e.ended_t_ms!).toBeGreaterThan(e.painted_t_ms!);
    });
    expect(events![0]!.shown_rgb).toHaveLength(3);
    expect(events![2]!.shown_rgb).toBeNull();
    expect(showTurnPrompt).toHaveBeenCalledWith("left", 1500);
  });

  it("holds each colour for at least its dwell", async () => {
    const { events } = await run(challenge(steps));
    for (const e of events!.filter((e) => e.step_id.startsWith("c"))) {
      expect(e.ended_t_ms! - e.painted_t_ms!).toBeGreaterThanOrEqual(300);
    }
  });

  it("marks a step skipped with its reason and no paint time", async () => {
    const reasons = ["fps_drop", null, null];
    const { events, overlay } = await run(challenge([colour("c0", 40, 0), colour("c1", 200, 1000)]),
      () => reasons.shift() ?? null);
    expect(events![0]).toEqual({ step_id: "c0", status: "skipped", painted_t_ms: null, ended_t_ms: null,
      shown_rgb: null, skip_reason: "fps_drop" });
    expect(events![1]!.status).toBe("shown");
    expect(overlay.changes).toHaveLength(2);
  });

  it("an fps drop skips the remaining colour steps but not the turn", async () => {
    const { events } = await run(challenge(steps), () => "fps_drop");
    expect(events!.map((e) => e.status)).toEqual(["skipped", "skipped", "shown", "skipped"]);
  });

  it.each([350, 0, 10, 15, 345, 359, -5, 370])("throws on red hue %i before painting anything", async (hue) => {
    const { error, overlay } = await run(challenge([colour("c0", 40, 0), colour("c1", hue, 1000)]));
    expect(String(error)).toMatch(/red/);
    expect(overlay.changes).toHaveLength(0);
  });

  it("never makes more than 3 colour changes in any second, even on a crowded schedule", async () => {
    const crowded = [0, 50, 100, 150, 200, 250].map((t, k) => colour(`c${k}`, 40 + 40 * k, t, 50));
    const { events, overlay } = await run(challenge(crowded));
    expect(events!.every((e) => e.status === "shown")).toBe(true);
    const c = overlay.changes;
    expect(c).toHaveLength(12);
    for (let i = 1; i < c.length; i++) expect(c[i]! - c[i - 1]!).toBeGreaterThanOrEqual(334);
    for (const t of c) expect(c.filter((s) => s >= t && s < t + 1000).length).toBeLessThanOrEqual(3);
  });
});

describe("isRedHue", () => {
  it("covers [345, 360) and [0, 15] only", () => {
    expect([345, 359.9, 0, 15, 720].map(isRedHue)).toEqual([true, true, true, true, true]);
    expect([15.1, 40, 300, 344.9].map(isRedHue)).toEqual([false, false, false, false]);
  });
});
