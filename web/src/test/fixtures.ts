// T22: one set of synthetic contract objects for the web unit tests (capture/session.test, console/console.test).
// Synthetic data only (AGENTS.md rule 10): no real faces, no real sessions.
import { vi } from "vitest";
import type { Challenge, ChallengeEvent, CheckResult, Decision, Plan, Preflight, SessionReport } from "../contracts";

/** A CAPABLE plan: light and turn both run. */
export const PLAN: Plan = { mode: "CAPABLE", run_light: true, run_turn: true, agent_questions: false, reasons: ["mode.capable.ok"] };

/** One colour step, then one turn. */
export const CHALLENGE: Challenge = {
  session_id: "s1", nonce: "n", mode: "CAPABLE", baseline_ms: 1500, total_ms: 6000,
  steps: [
    { kind: "colour", step_id: "c0", hue_deg: 40, start_offset_ms: 0, dwell_ms: 400 },
    { kind: "turn", step_id: "t0", direction: "left", start_offset_ms: 1000, duration_ms: 3000 },
  ],
};

/** Both CHALLENGE steps shown. */
export const EVENTS: ChallengeEvent[] = [
  { step_id: "c0", status: "shown", painted_t_ms: 1510, ended_t_ms: 1920, shown_rgb: [0.5, 0.5, 0.4], skip_reason: null },
  { step_id: "t0", status: "shown", painted_t_ms: 2510, ended_t_ms: 5520, shown_rgb: null, skip_reason: null },
];

/** A desktop preflight at 10 fps with a face found. */
export const PREFLIGHT: Preflight = {
  user_agent: "u", platform: "desktop", browser: "Brave 155", camera_label: "c", width: 640, height: 480,
  measured_fps: 10, dropped_frame_ratio: 0, blur: 0, brightness: 0, face_found: true, face_fraction: 0.1,
  controls: [], gyro: false, no_flash_requested: false, clock: "now", probe: [],
};

/** One check result: a flagged sensor.duplicates unless overridden. */
export const check = (over: Partial<CheckResult> = {}): CheckResult => ({
  check_id: "sensor.duplicates", family: "B", vote_group: "B.stream", status: "usable", risk: 0.9, flag: true,
  quality: 1, explanation: "110 of 152 frames repeated the one before (72.4%; limit 5%).",
  threshold_source: "provisional", ...over,
});

/** HUMAN_REVIEW: families B and C flag, A not run, D abstained. */
export const DECISION: Decision = {
  outcome: "HUMAN_REVIEW", step_up: null, integrity_violation: false, provisional: true, decided_at_ms: 1,
  reasons: ["Two independent kinds of evidence raised risk, so a person must review it."],
  families: [
    { family: "A", state: "not_run", usable_checks: 0, flagged_checks: 0, reasons: [] },
    { family: "B", state: "flag", usable_checks: 1, flagged_checks: 1, reasons: [] },
    { family: "C", state: "flag", usable_checks: 1, flagged_checks: 1, reasons: [] },
    { family: "D", state: "abstained", usable_checks: 0, flagged_checks: 0, reasons: [] },
  ],
};

/**
 * A finished CONSTRAINED session for the agent console: two colours (the second skipped for an fps drop) and a turn,
 * four check results and the DECISION above. Matches console.test's REPORT; `over` replaces top-level fields.
 */
export function report(over: Partial<SessionReport> = {}): SessionReport {
  return {
    session_id: "d79105c5121a3cb3", product: "instant_loan", attempt: 1, state: "done", label: null,
    preflight: PREFLIGHT,
    plan: { mode: "CONSTRAINED", run_light: true, run_turn: true, agent_questions: false, reasons: ["mode.constrained.fps"] },
    challenge: {
      session_id: "d79105c5121a3cb3", nonce: "n", mode: "CONSTRAINED", baseline_ms: 1500, total_ms: 9000,
      steps: [
        { kind: "colour", step_id: "c0", hue_deg: 40, start_offset_ms: 0, dwell_ms: 700 },
        { kind: "colour", step_id: "c1", hue_deg: 200, start_offset_ms: 2000, dwell_ms: 700 },
        { kind: "turn", step_id: "t0", direction: "left", start_offset_ms: 4000, duration_ms: 3500 },
      ],
    },
    events: [
      { step_id: "c0", status: "shown", painted_t_ms: 1510, ended_t_ms: 2210, shown_rgb: [0.6, 0.5, 0.3] },
      { step_id: "c1", status: "skipped", painted_t_ms: null, ended_t_ms: null, shown_rgb: null, skip_reason: "fps_drop" },
      { step_id: "t0", status: "shown", painted_t_ms: 5500, ended_t_ms: 9000, shown_rgb: null },
    ],
    frame_count: 100,
    results: [
      check(),
      check({ check_id: "light.response", family: "C", vote_group: "C.response", explanation: "The face answered 1 of 6." }),
      check({ check_id: "turn.follow", family: "D", vote_group: "D.turn", status: "abstain", risk: null, flag: false,
        explanation: "The face was lost during the turn.", reason_codes: ["quality.no_face"] }),
      check({ check_id: "fake.b", family: "B", vote_group: "B.fake", flag: false, risk: 0,
        explanation: "FAKE ANALYSIS: not a real measurement." }),
    ],
    decision: DECISION,
    agent_decision: null,
    ...over,
  };
}

/**
 * Drives a started CaptureSession to its end under fake timers: let it reach the upload flush, release the flush,
 * run every remaining timer, then await the session. Call as `await runToEnd(st, s.start(false))`.
 */
export async function runToEnd(st: { releaseFlush: () => void }, done: Promise<unknown>): Promise<void> {
  await vi.advanceTimersByTimeAsync(0);
  st.releaseFlush();
  await vi.runAllTimersAsync();
  await done;
}
