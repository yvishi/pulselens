import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../api/client";
import type { Challenge, ChallengeEvent, CustomerStatus, Plan, Preflight } from "../contracts";
import type { GrabberOptions } from "./grabber";
import { CaptureSession, type CaptureSessionDeps, type CaptureState } from "./session";

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

/** Every dependency stubbed; each call is logged by name, in order. */
function stubs(over: Partial<CaptureSessionDeps> = {}) {
  const log: string[] = [];
  const statuses: CustomerStatus[] = [
    { state: "analysing", message: "please_wait" },
    { state: "analysing", message: "please_wait" },
    { state: "done", message: "continue" },
  ];
  let grabberOpts: GrabberOptions | null = null;
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
      };
    }),
    createUploader: vi.fn(() => uploader),
    runChallenge: vi.fn(async (_ch, d) => {
      log.push(`runChallenge(t0=${d.t0})`);
      expect(d.shouldSkipLight()).toBeNull();
      return EVENTS;
    }),
    now: () => 1234,
    sleep: (ms: number) => new Promise((r) => setTimeout(r, ms)),
    ...over,
  };
  return { deps, log, uploader, overlay, grabberOpts: () => grabberOpts, releaseFlush: () => flushRelease?.() };
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
});
