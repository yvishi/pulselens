import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { now } from "../../capture/clock";
import { createFaceTracker, type FaceTracker } from "../../capture/face";
import { defaultDeps } from "../../capture/session";
import type { TurnPromptContext } from "../../capture/turnPrompt";
import { ringTurnPrompt } from "./TurnPrompt";

vi.mock("../../capture/face", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../capture/face")>()),
  createFaceTracker: vi.fn(async () => ({ detect: () => ({ found: true, box: null, yawDeg: 5 }) })),
}));

function context(): TurnPromptContext & { prompts: (string | null)[] } {
  const prompts: (string | null)[] = [];
  return {
    prompts,
    overlay: { t0: now(), showPrompt: (s) => prompts.push(s) },
    video: document.createElement("video"),
    text: (dir) => `Turn your head to your ${dir.toUpperCase()}, then back to the centre`,
  };
}

/** A tracker whose yaw rises by 2 deg per detect call. */
function stubTracker(): FaceTracker & { calls: number } {
  const t = {
    calls: 0,
    detect: () => ({ found: true, box: null, yawDeg: 2 * t.calls++ }),
  };
  return t;
}

beforeEach(() => vi.useFakeTimers());
afterEach(() => {
  vi.useRealTimers();
  document.body.innerHTML = "";
});

describe("ringTurnPrompt", () => {
  it("resolves after duration_ms with painted <= ended, and fills the ring from the tracker", async () => {
    const tracker = stubTracker();
    const ctx = context();
    const show = ringTurnPrompt({ loadTracker: async () => tracker })(ctx);
    await vi.advanceTimersByTimeAsync(0); // tracker loads
    const p = show("left", 2000);
    await vi.advanceTimersByTimeAsync(100);
    const root = document.querySelector<HTMLElement>("[data-turn-prompt]")!;
    expect(root).not.toBeNull();
    expect(root.dataset.turnPrompt).toBe("left");
    expect(root.textContent).toContain("Turn your head to your LEFT, then back to the centre");
    expect(root.querySelector("[data-arrow]")!.getAttribute("data-arrow")).toBe("left");
    expect(root.querySelector("[data-ring]")).not.toBeNull();
    await vi.advanceTimersByTimeAsync(1500);
    expect(Number(root.querySelector<HTMLElement>("[data-ring]")!.dataset.progress)).toBeGreaterThan(0);
    await vi.advanceTimersByTimeAsync(1000);
    const { painted, ended } = await p;
    expect(painted).toBeLessThanOrEqual(ended);
    expect(ended - painted).toBeGreaterThanOrEqual(2000);
    expect(document.querySelector("[data-turn-prompt]")).toBeNull(); // removed
    expect(ctx.video.style.zIndex).toBe(""); // self-view put back
    const calls = tracker.calls;
    await vi.advanceTimersByTimeAsync(500);
    expect(tracker.calls).toBe(calls); // stopped detecting
  });

  it("falls back to the text prompt when the face tracker cannot load", async () => {
    const ctx = context();
    const show = ringTurnPrompt({ loadTracker: () => Promise.reject(new Error("no wasm")) })(ctx);
    await vi.advanceTimersByTimeAsync(0);
    const p = show("right", 1000);
    await vi.advanceTimersByTimeAsync(50);
    expect(document.querySelector("[data-ring]")).toBeNull();
    expect(ctx.prompts.at(-1)).toContain("RIGHT");
    await vi.advanceTimersByTimeAsync(1100);
    const { painted, ended } = await p;
    expect(painted).toBeLessThanOrEqual(ended);
    expect(ctx.prompts.at(-1)).toBeNull();
  });

  it("shows the prompt without a ring while the tracker is still loading", async () => {
    const ctx = context();
    const show = ringTurnPrompt({ loadTracker: () => new Promise<FaceTracker>(() => undefined) })(ctx);
    const p = show("right", 800);
    await vi.advanceTimersByTimeAsync(50);
    const root = document.querySelector<HTMLElement>("[data-turn-prompt]")!;
    expect(root.querySelector("[data-arrow]")!.getAttribute("data-arrow")).toBe("right");
    expect(root.querySelector("[data-ring]")).toBeNull();
    await vi.advanceTimersByTimeAsync(900);
    await p;
  });
});

describe("one face tracker per session", () => {
  it("the ring prompt reuses the session's shared tracker: createFaceTracker is called once", async () => {
    const deps = defaultDeps();
    const video = document.createElement("video");
    void deps.faceTracker(); // the preflight's tracker
    deps.createCoachMeter(video); // the coaching meter's tracker
    const show = ringTurnPrompt()({ ...context(), faceTracker: deps.faceTracker });
    await vi.advanceTimersByTimeAsync(0); // tracker loads
    const p = show("left", 500);
    await vi.advanceTimersByTimeAsync(100);
    expect(document.querySelector("[data-ring]")).not.toBeNull(); // the shared tracker drives the ring
    await vi.advanceTimersByTimeAsync(600);
    await p;
    expect(vi.mocked(createFaceTracker)).toHaveBeenCalledTimes(1);
  });
});
