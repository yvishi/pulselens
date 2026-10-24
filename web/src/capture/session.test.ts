import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../api/client";
import type { Challenge, ChallengeEvent, CustomerStatus, Plan, Preflight } from "../contracts";
import type { CoachMetrics } from "./coaching";
import type { GrabberOptions } from "./grabber";
import type { UploaderOptions, UploaderStats } from "./uploader";
import { cameraError, CaptureSession, type CaptureSessionDeps, type CaptureState } from "./session";

const PLAN: Plan = { mode: "CAPABLE", run_light: true, run_turn: true, agent_questions: false, reasons: ["mode.capable.ok"] };
const CHALLENGE: Challenge = {
  session_id: "s1", nonce: "n", mode: "CAPABLE", baseline_ms: 1500, total_ms: 6000,
  steps: [
    { kind: "colour", step_id: "c0", hue_deg: 40, start_offset_ms: 0, dwell_ms: 400 },
    { kind: "turn", step_id: "t0", direction: "left", start_offset_ms: 1000, duration_ms: 3000 },
  ],
};
const EVENTS: ChallengeEvent[] = [
  { step_id: "c0", status: "shown", painted_t_ms: 1510, ended_t_ms: 1920, shown_rgb: [0.5, 0.5, 0.4], skip_reason: null },
  { step_id: "t0", status: "shown", painted_t_ms: 2510, ended_t_ms: 5520, shown_rgb: null, skip_reason: null },
];

const GOOD: CoachMetrics = {
  brightness: 120, faceLuma: 120, outsideLuma: 110, faceFraction: 0.1, faceBottom: 0.5, blur: 100, blurBaseline: 100,
};
const DARK: CoachMetrics = { ...GOOD, brightness: 20, faceLuma: 20, outsideLuma: 20 };

/** Every dependency stubbed; each call is logged by name, in order. */
function stubs(over: Partial<CaptureSessionDeps> = {}) {
  const log: string[] = [];
  const statuses: CustomerStatus[] = [
    { state: "analysing", message: "please_wait" },
    { state: "analysing", message: "please_wait" },
    { state: "done", message: "continue" },
  ];
  let grabberOpts: GrabberOptions | null = null;
  let uploaderOpts: UploaderOptions | null = null;
  const fps = { now: 30 as number | null };
  let flushRelease: (() => void) | null = null;
  const uploader = {
    push: vi.fn(),
    flush: vi.fn(() => {
      log.push("flush");
      return new Promise<void>((r) => (flushRelease = () => { log.push("flushed"); r(); }));
    }),
    stop: vi.fn(async () => void log.push("uploader.stop")),
    stats: () => ({ sent: 0, dropped: 0, failedBatches: 0 }),
  };
  const overlay = { t0: 0, paint: vi.fn(), clear: vi.fn(), showPrompt: vi.fn(), dispose: vi.fn(() => log.push("overlay.dispose")) };
  const deps: CaptureSessionDeps = {
    api: {
      postPreflight: vi.fn(async (_id: string, _t: string, pf: Preflight) => {
        log.push(`postPreflight(no_flash=${pf.no_flash_requested})`);
        return PLAN;
      }),
      getChallenge: vi.fn(async () => (log.push("getChallenge"), CHALLENGE)),
      postFrames: vi.fn(async () => undefined),
      postEvents: vi.fn(async (_id: string, _t: string, ev: ChallengeEvent[]) => void log.push(`postEvents(${ev.length})`)),
      completeSession: vi.fn(async () => void log.push("complete")),
      getStatus: vi.fn(async () => (log.push("getStatus"), statuses.length > 1 ? statuses.shift()! : statuses[0]!)),
    },
    secureContextError: () => null,
    isMobile: () => false,
    openCamera: vi.fn(async () => {
      log.push("openCamera");
      return { stream: {} as MediaStream, track: {} as MediaStreamTrack, settings: {} };
    }),
    stopCamera: vi.fn(() => void log.push("stopCamera")),
    runPreflight: vi.fn(async (_v, _c, opts: { noFlashRequested: boolean }) => {
      log.push("runPreflight");
      return { no_flash_requested: opts.noFlashRequested } as Preflight;
    }),
    chooseOverlayMode: vi.fn(async () => (log.push("chooseOverlayMode"), "fullscreen" as const)),
    createOverlay: vi.fn(() => (log.push("createOverlay"), overlay)),
    createGrabber: vi.fn((_v: HTMLVideoElement, o: GrabberOptions) => {
      grabberOpts = o;
      return {
        start: () => void log.push("grabber.start"),
        stop: () => void log.push("grabber.stop"),
        close: () => void log.push("grabber.close"),
        stats: () => ({ frames: 0, medianFps: 30, droppedRatio: 0, clock: "now" as const }),
        fpsOver: () => fps.now,
      };
    }),
    createUploader: vi.fn((o: UploaderOptions) => ((uploaderOpts = o), uploader)),
    runChallenge: vi.fn(async (_ch, d) => {
      log.push(`runChallenge(t0=${d.t0})`);
      expect(d.shouldSkipLight()).toBeNull();
      return EVENTS;
    }),
    createCoachMeter: vi.fn(() => ({ measure: vi.fn(async () => GOOD) })),
    faceTracker: vi.fn(async () => null),
    shouldLock: vi.fn(() => false),
    lockForLight: vi.fn(async () => {
      log.push("lock");
      return { lock: null, restore: async () => void log.push("restore") };
    }),
    now: () => 1234,
    sleep: (ms: number) => new Promise((r) => setTimeout(r, ms)),
    ...over,
  };
  return {
    deps, log, uploader, overlay, fps, grabberOpts: () => grabberOpts, releaseFlush: () => flushRelease?.(),
    reportUploads: (st: Partial<UploaderStats>) => uploaderOpts!.onStats!({ sent: 0, dropped: 0, failedBatches: 0, ...st }),
  };
}

function session(deps: CaptureSessionDeps) {
  const states: CaptureState[] = [];
  const s = new CaptureSession({
    sessionId: "s1", token: "tok", video: document.createElement("video"), overlayRoot: document.body,
    onState: (st) => states.push(st), deps,
  });
  return { s, states, phases: () => states.map((st) => st.phase) };
}

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

describe("CaptureSession", () => {
  it("runs camera, preflight, challenge, upload, complete and polls to a result, in order", async () => {
    const st = stubs();
    const { s, states, phases } = session(st.deps);
    const done = s.start(false);
    await vi.advanceTimersByTimeAsync(500);
    expect(st.log).toContain("flush");
    expect(st.log).not.toContain("complete"); // never while a batch may be in flight
    st.releaseFlush();
    await vi.runAllTimersAsync();
    await done;
    expect(st.log).toEqual([
      "chooseOverlayMode", "openCamera", "runPreflight", "postPreflight(no_flash=false)", "getChallenge",
      "createOverlay", "grabber.start", "runChallenge(t0=1234)", "grabber.stop", "overlay.dispose",
      "postEvents(2)", "flush", "flushed", "uploader.stop", "stopCamera", "complete",
      "getStatus", "getStatus", "getStatus", "grabber.close",
    ]);
    expect(phases()).toEqual(["camera", "preflight", "challenge", "uploading", "waiting", "result"]);
    expect(states.at(-1)).toMatchObject({ phase: "result", detail: "continue" });
    expect(st.grabberOpts()).toMatchObject({ size: [640, 480], t0: 1234 });
  });

  it("hands the session's one face tracker to the turn prompt", async () => {
    const st = stubs();
    const turnPrompt = vi.fn(() => async () => ({ painted: 0, ended: 0 }));
    const s = new CaptureSession({
      sessionId: "s1", token: "tok", video: document.createElement("video"), overlayRoot: document.body,
      onState: () => undefined, deps: st.deps, turnPrompt,
    });
    const done = s.start(false);
    await vi.advanceTimersByTimeAsync(0);
    st.releaseFlush();
    await vi.runAllTimersAsync();
    await done;
    expect(turnPrompt).toHaveBeenCalledWith(expect.objectContaining({ faceTracker: st.deps.faceTracker }));
  });

  it("feeds every grabbed frame to the uploader", async () => {
    const st = stubs();
    const { s } = session(st.deps);
    const done = s.start(false);
    await vi.advanceTimersByTimeAsync(0);
    const f = { idx: 0, t_ms: 1, w: 640, h: 480, jpeg: new Blob() };
    st.grabberOpts()!.onFrame(f);
    expect(st.uploader.push).toHaveBeenCalledWith(f);
    st.releaseFlush();
    await vi.runAllTimersAsync();
    await done;
  });

  it("passes the no-flash choice into the preflight and uses the mobile size on phones", async () => {
    const st = stubs({ isMobile: () => true });
    const { s } = session(st.deps);
    const done = s.start(true);
    await vi.advanceTimersByTimeAsync(0);
    st.releaseFlush();
    await vi.runAllTimersAsync();
    await done;
    expect(st.log).toContain("postPreflight(no_flash=true)");
    expect(st.grabberOpts()!.size).toEqual([480, 360]);
  });

  it("caps the flush at 15 s, then stops the uploader before completing", async () => {
    const st = stubs();
    const { s, phases } = session(st.deps);
    const done = s.start(false);
    await vi.advanceTimersByTimeAsync(14_000);
    expect(st.log).not.toContain("complete");
    await vi.runAllTimersAsync();
    await done;
    const i = st.log.indexOf("uploader.stop");
    expect(i).toBeGreaterThan(st.log.indexOf("flush"));
    expect(st.log.indexOf("complete")).toBeGreaterThan(i);
    expect(phases().at(-1)).toBe("result");
  });

  it("a denied camera ends in the error phase without a preflight", async () => {
    const denied = Object.assign(new Error("denied"), { name: "NotAllowedError" });
    const st = stubs({ openCamera: vi.fn(async () => { throw denied; }) });
    const { s, states } = session(st.deps);
    await s.start(false);
    expect(states.map((x) => x.phase)).toEqual(["camera", "error"]);
    expect(states.at(-1)!.detail).toBe("camera_denied");
    expect(st.deps.runPreflight).not.toHaveBeenCalled();
  });

  it("an expired session is an error, never a result", async () => {
    const st = stubs();
    st.deps.api.getChallenge = vi.fn(async () => { throw new ApiError(410, "session_expired"); });
    const { s, states } = session(st.deps);
    await s.start(false);
    expect(states.at(-1)).toEqual({ phase: "error", detail: "expired" });
    expect(st.log).toContain("stopCamera");
  });

  it("skips light steps while the page is hidden", async () => {
    let reason: string | null = "unset";
    const st = stubs({
      runChallenge: vi.fn(async (_ch, d) => {
        Object.defineProperty(document, "hidden", { value: true, configurable: true });
        reason = d.shouldSkipLight();
        Object.defineProperty(document, "hidden", { value: false, configurable: true });
        return EVENTS;
      }),
    });
    const { s } = session(st.deps);
    const done = s.start(false);
    await vi.advanceTimersByTimeAsync(0);
    st.releaseFlush();
    await vi.runAllTimersAsync();
    await done;
    expect(reason).toBe("page_hidden");
  });

  it("no tips: no coaching screen and a single preflight", async () => {
    const st = stubs();
    const { s, phases } = session(st.deps);
    const done = s.start(false);
    await vi.advanceTimersByTimeAsync(0);
    st.releaseFlush();
    await vi.runAllTimersAsync();
    await done;
    expect(phases()).not.toContain("coaching");
    expect(st.deps.runPreflight).toHaveBeenCalledTimes(1);
  });

  it("coaches up to 3 rounds, then continues anyway with a fresh preflight", async () => {
    const measure = vi.fn(async () => DARK);
    const st = stubs({ createCoachMeter: vi.fn(() => ({ measure })) });
    const { s, states, phases } = session(st.deps);
    const done = s.start(false);
    await vi.advanceTimersByTimeAsync(0);
    st.releaseFlush();
    await vi.runAllTimersAsync();
    await done;
    expect(phases().slice(0, 7)).toEqual(["camera", "preflight", "coaching", "coaching", "coaching", "preflight", "challenge"]);
    expect(states.filter((x) => x.phase === "coaching").map((x) => x.tips)).toEqual([["light"], ["light"], ["light"]]);
    expect(measure).toHaveBeenCalledTimes(4); // with the preflight, then once per round
    expect(measure.mock.calls.slice(1).map((c) => (c as unknown[])[0])).toEqual([3000, 3000, 3000]);
    expect(st.deps.runPreflight).toHaveBeenCalledTimes(2);
    expect(phases().at(-1)).toBe("result");
  });

  it("stops coaching as soon as the tips clear", async () => {
    const results = [DARK, GOOD];
    const st = stubs({ createCoachMeter: vi.fn(() => ({ measure: vi.fn(async () => results.shift() ?? GOOD) })) });
    const { s, phases } = session(st.deps);
    const done = s.start(false);
    await vi.advanceTimersByTimeAsync(0);
    st.releaseFlush();
    await vi.runAllTimersAsync();
    await done;
    expect(phases().slice(0, 5)).toEqual(["camera", "preflight", "coaching", "preflight", "challenge"]);
  });

  it("a NO_FLASH plan skips every colour step and asks the agent's questions", async () => {
    let reason: string | null = "unset";
    const st = stubs({
      runChallenge: vi.fn(async (_ch, d) => {
        reason = d.shouldSkipLight();
        return EVENTS;
      }),
    });
    st.deps.api.postPreflight = vi.fn(async () => ({
      mode: "NO_FLASH" as const, run_light: false, run_turn: true, agent_questions: true, reasons: ["mode.no_flash.requested"],
    }));
    const { s, states } = session(st.deps);
    const done = s.start(true);
    await vi.advanceTimersByTimeAsync(0);
    st.releaseFlush();
    await vi.runAllTimersAsync();
    await done;
    expect(reason).toBe("no_flash");
    expect(states.at(-1)).toMatchObject({ phase: "result", agentQuestions: true });
  });

  it("an fps drop during the challenge skips the remaining colour steps (the grabber's fps over the last 2 s < 12)", async () => {
    const reasons: (string | null)[] = [];
    const st = stubs({
      runChallenge: vi.fn(async (_ch, d) => {
        reasons.push(d.shouldSkipLight());
        st.fps.now = 8;
        reasons.push(d.shouldSkipLight());
        st.fps.now = 30; // a recovery does not bring the colours back
        reasons.push(d.shouldSkipLight());
        return EVENTS;
      }),
    });
    const { s } = session(st.deps);
    const done = s.start(false);
    await vi.advanceTimersByTimeAsync(0);
    st.releaseFlush();
    await vi.runAllTimersAsync();
    await done;
    expect(reasons).toEqual([null, "fps_drop", "fps_drop"]);
  });

  it("says the connection is weak after 2 failed batches, without changing the phase", async () => {
    const seen: CaptureState[] = [];
    const st = stubs({
      runChallenge: vi.fn(async () => {
        st.reportUploads({ failedBatches: 1 });
        seen.push({ ...states.at(-1)! });
        st.reportUploads({ failedBatches: 2 });
        seen.push({ ...states.at(-1)! });
        return EVENTS;
      }),
    });
    const { s, states } = session(st.deps);
    const done = s.start(false);
    await vi.advanceTimersByTimeAsync(0);
    expect(states.at(-1)).toMatchObject({ phase: "uploading", weakConnection: true });
    st.releaseFlush();
    await vi.runAllTimersAsync();
    await done;
    expect(seen[0]).toMatchObject({ phase: "challenge" });
    expect(seen[0]!.weakConnection).toBeFalsy();
    expect(seen[1]).toMatchObject({ phase: "challenge", weakConnection: true });
    expect(states.at(-1)).toMatchObject({ phase: "result", detail: "continue" });
  });

  it.each([
    ["NotAllowedError", "camera_denied"],
    ["SecurityError", "camera_denied"],
    ["NotFoundError", "camera_missing"],
    ["NotReadableError", "camera_busy"],
    ["AbortError", "camera_busy"],
    ["OverconstrainedError", "camera_error"],
    ["TypeError", "camera_error"],
  ])("a camera %s ends in the %s error, once, with no retry", async (name, detail) => {
    const err = Object.assign(new Error(name), { name });
    const st = stubs({ openCamera: vi.fn(async () => { throw err; }) });
    const { s, states } = session(st.deps);
    await s.start(false);
    expect(states.map((x) => x.phase)).toEqual(["camera", "error"]);
    expect(states.at(-1)!.detail).toBe(detail);
    expect(st.deps.openCamera).toHaveBeenCalledTimes(1);
    expect(cameraError(err)).toBe(detail);
  });

  it("cameraError copes with odd throws", () => {
    expect(cameraError(null)).toBe("camera_error");
    expect(cameraError("denied")).toBe("camera_error");
  });

  it("?lock=1: locks the camera around the challenge and restores it afterwards", async () => {
    const st = stubs({ shouldLock: vi.fn(() => true) });
    st.deps.runPreflight = vi.fn(async () => ({ no_flash_requested: false, measured_fps: 10.4 }) as Preflight);
    const { s } = session(st.deps);
    const done = s.start(false);
    await vi.advanceTimersByTimeAsync(0);
    st.releaseFlush();
    await vi.runAllTimersAsync();
    await done;
    expect(st.deps.lockForLight).toHaveBeenCalledWith(expect.anything(), 10.4);
    const i = st.log.indexOf("runChallenge(t0=1234)");
    expect(st.log.indexOf("lock")).toBeLessThan(i);
    expect(st.log.indexOf("restore")).toBeGreaterThan(i);
    expect(st.log.indexOf("restore")).toBeLessThan(st.log.indexOf("stopCamera"));
  });

  it("no lock without the flag, or on a no-flash plan", async () => {
    const plain = stubs();
    const a = session(plain.deps);
    const d1 = a.s.start(false);
    await vi.advanceTimersByTimeAsync(0);
    plain.releaseFlush();
    await vi.runAllTimersAsync();
    await d1;
    expect(plain.deps.lockForLight).not.toHaveBeenCalled();

    const nf = stubs({ shouldLock: vi.fn(() => true) });
    nf.deps.api.postPreflight = vi.fn(async () => ({
      mode: "NO_FLASH" as const, run_light: false, run_turn: true, agent_questions: true, reasons: ["mode.no_flash.requested"],
    }));
    const b = session(nf.deps);
    const d2 = b.s.start(true);
    await vi.advanceTimersByTimeAsync(0);
    nf.releaseFlush();
    await vi.runAllTimersAsync();
    await d2;
    expect(nf.deps.lockForLight).not.toHaveBeenCalled();
  });
});
