import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { CheckResult, Decision, SessionReport, SessionSummary } from "../contracts";

const api = vi.hoisted(() => ({
  listSessions: vi.fn(),
  getResult: vi.fn(),
  postAgentDecision: vi.fn(),
  createSession: vi.fn(),
}));
vi.mock("qrcode", () => ({ default: { toCanvas: vi.fn().mockResolvedValue(undefined) } }));
vi.mock("../api/client", async (orig) => ({ ...(await orig<typeof import("../api/client")>()), ...api }));

const { ApiError } = await import("../api/client");
const { ConsoleList, visibleRows } = await import("./ConsoleList");
const { ConsoleSession } = await import("./ConsoleSession");
const { FamilyCard } = await import("./FamilyCard");
const { pickEvidenceFrames } = await import("./EvidenceFrames");
const { alignSeries } = await import("./CheckPlot");

const check = (over: Partial<CheckResult>): CheckResult => ({
  check_id: "sensor.duplicates", family: "B", vote_group: "B.stream", status: "usable", risk: 0.9, flag: true,
  quality: 1, explanation: "110 of 152 frames repeated the one before (72.4%; limit 5%).",
  threshold_source: "provisional", ...over,
});

const DECISION: Decision = {
  outcome: "HUMAN_REVIEW", step_up: null, integrity_violation: false, provisional: true, decided_at_ms: 1,
  reasons: ["Two independent kinds of evidence raised risk, so a person must review it."],
  families: [
    { family: "A", state: "not_run", usable_checks: 0, flagged_checks: 0, reasons: [] },
    { family: "B", state: "flag", usable_checks: 1, flagged_checks: 1, reasons: [] },
    { family: "C", state: "flag", usable_checks: 1, flagged_checks: 1, reasons: [] },
    { family: "D", state: "abstained", usable_checks: 0, flagged_checks: 0, reasons: [] },
  ],
};

const REPORT: SessionReport = {
  session_id: "d79105c5121a3cb3", product: "instant_loan", attempt: 1, state: "done", label: null,
  preflight: {
    user_agent: "u", platform: "desktop", browser: "Brave 155", camera_label: "c", width: 640, height: 480,
    measured_fps: 10, dropped_frame_ratio: 0, blur: 0, brightness: 0, face_found: true, face_fraction: 0.1,
    controls: [], gyro: false, no_flash_requested: false, clock: "now", probe: [],
  },
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
    check({}),
    check({ check_id: "light.response", family: "C", vote_group: "C.response", explanation: "The face answered 1 of 6." }),
    check({ check_id: "turn.follow", family: "D", vote_group: "D.turn", status: "abstain", risk: null, flag: false,
      explanation: "The face was lost during the turn.", reason_codes: ["quality.no_face"] }),
    check({ check_id: "fake.b", family: "B", vote_group: "B.fake", flag: false, risk: 0,
      explanation: "FAKE ANALYSIS: not a real measurement." }),
  ],
  decision: DECISION,
  agent_decision: null,
};

beforeEach(() => {
  sessionStorage.clear();
  Object.values(api).forEach((f) => f.mockReset());
  vi.stubGlobal("fetch", vi.fn(async () => new Response("", { status: 404 })));
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function at(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/console" element={<ConsoleList />} />
        <Route path="/console/:sessionId" element={<ConsoleSession />} />
      </Routes>
    </MemoryRouter>,
  );
}

function enterPasscode(value = "pc") {
  fireEvent.change(screen.getByLabelText("Agent passcode"), { target: { value } });
  fireEvent.click(screen.getByRole("button", { name: "Open console" }));
}

describe("ConsoleList", () => {
  it("asks for the passcode once, then lists sessions with their outcome", async () => {
    const row: SessionSummary = {
      session_id: "abc", created_at_ms: 0, product: "savings_account", attempt: 1, state: "done", mode: "CAPABLE",
      outcome: "PASS", label_kind: "genuine",
    };
    api.listSessions.mockResolvedValue([row]);
    at("/console");
    expect(api.listSessions).not.toHaveBeenCalled();
    enterPasscode("secret");
    const table = await screen.findByRole("table", { name: "Sessions" });
    expect(api.listSessions).toHaveBeenCalledWith("secret");
    expect(within(table).getByRole("link", { name: "abc" }).getAttribute("href")).toBe("/console/abc");
    expect(table.textContent).toContain("PASS");
    expect(sessionStorage.getItem("pulselens.agent_passcode")).toBe("secret");
  });

  it("asks again when the passcode is refused", async () => {
    api.listSessions.mockRejectedValue(new ApiError(401, "unauthorized"));
    at("/console");
    enterPasscode("wrong");
    expect((await screen.findByRole("alert")).textContent).toMatch(/not accepted/);
    expect(screen.getByLabelText("Agent passcode")).toBeTruthy();
  });

  it("says so when the server is unreachable", async () => {
    sessionStorage.setItem("pulselens.agent_passcode", "pc");
    api.listSessions.mockRejectedValue(new TypeError("Failed to fetch"));
    at("/console");
    expect((await screen.findByRole("alert")).textContent).toMatch(/unreachable/);
  });
});

describe("ConsoleSession", () => {
  beforeEach(() => sessionStorage.setItem("pulselens.agent_passcode", "pc"));

  it("shows the outcome, honesty labels, plan reasons and families with failed and abstained apart", async () => {
    api.getResult.mockResolvedValue(REPORT);
    at("/console/d79105c5121a3cb3");
    const banner = await screen.findByRole("region", { name: "Outcome" });
    expect(banner.textContent).toContain("HUMAN REVIEW");
    expect(banner.textContent).toContain("PulseLens recommends; the agent decides.");
    expect(screen.getByText("PROVISIONAL THRESHOLDS")).toBeTruthy();
    expect(screen.getByText("FAKE ANALYSIS")).toBeTruthy();
    expect(screen.getByText(/fewer frames than a full challenge needs/)).toBeTruthy();
    const b = screen.getByRole("region", { name: "Family B: Sensor and stream" });
    expect(within(b).getByText("FLAG")).toBeTruthy();
    expect(within(b).getByText("Raised risk").parentElement!.textContent).toContain("72.4%");
    expect(within(b).getByText("Checked, no risk").parentElement!.textContent).toContain("FAKE ANALYSIS");
    const d = screen.getByRole("region", { name: "Family D: Visual and motion" });
    expect(within(d).getByText("ABSTAINED")).toBeTruthy();
    expect(within(d).getByText("Could not judge").parentElement!.textContent).toContain("lost during the turn");
    expect(within(d).queryByText("Raised risk")).toBeNull();
    const a = screen.getByRole("region", { name: "Family A: Pulse" });
    expect(a.textContent).toContain("not used in the decision");
    const timeline = screen.getByRole("region", { name: "Challenge timeline" });
    expect(timeline.textContent).toContain("1 skipped");
  });

  it("records an approval and refreshes", async () => {
    api.getResult.mockResolvedValueOnce(REPORT).mockResolvedValue({ ...REPORT, agent_decision: { action: "approve", note: "ok" } });
    api.postAgentDecision.mockResolvedValue(undefined);
    at("/console/d79105c5121a3cb3");
    fireEvent.change(await screen.findByLabelText("Note"), { target: { value: "ok" } });
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Approve" })));
    expect(api.postAgentDecision).toHaveBeenCalledWith("d79105c5121a3cb3", "pc", { action: "approve", note: "ok" });
    await waitFor(() => expect(screen.getByRole("status").textContent).toMatch(/^Approved/));
  });

  it("re-verify creates the next attempt and shows its customer link", async () => {
    api.getResult.mockResolvedValue(REPORT);
    api.postAgentDecision.mockResolvedValue(undefined);
    api.createSession.mockResolvedValue({ customer_url: "/customer/next?t=tok" });
    const { container } = at("/console/d79105c5121a3cb3");
    const reverify = await screen.findByRole("button", { name: "Re-verify" });
    await act(async () => fireEvent.click(reverify));
    expect(api.createSession).toHaveBeenCalledWith({ product: "instant_loan", previous_session_id: "d79105c5121a3cb3" });
    expect((await screen.findByRole("link", { name: /customer\/next/ })).getAttribute("href")).toContain("/customer/next?t=tok");
    expect(container.querySelector(".next-link canvas")).not.toBeNull();
    expect(screen.getByRole("button", { name: "Copy link" })).toBeTruthy();
  });

  it("keeps the actions closed until a decision exists", async () => {
    api.getResult.mockResolvedValue({ ...REPORT, decision: null, state: "analysing" });
    at("/console/d79105c5121a3cb3");
    expect((await screen.findByRole("button", { name: "Approve" })).hasAttribute("disabled")).toBe(true);
    expect(screen.getByRole("region", { name: "Outcome" }).textContent).toContain("Analysing");
  });
});

describe("FamilyCard", () => {
  it("says Analysing… and invents no state while there is no summary", () => {
    render(<FamilyCard family="B" summary={null} results={[]} />);
    const chip = screen.getByText("Analysing…");
    expect(chip.className).toContain("state-pending");
    expect(screen.getByRole("region", { name: "Family B: Sensor and stream" }).className).toContain("family-pending");
  });
});

describe("helpers", () => {
  it("picks one frame per shown colour step and one in the middle of the turn", () => {
    const frames = pickEvidenceFrames(REPORT);
    expect(frames).toEqual([
      { kind: "colour", label: "c0 (hue 40°)", idx: 15 }, // 1510 ms at 10 fps
      { kind: "turn", label: "t0 turn left", idx: 73 }, // painted 5500 + 3500 / 2 = 7250 ms
    ]);
    expect(pickEvidenceFrames({ ...REPORT, frame_count: 0 })).toEqual([]);
  });

  it("merges plot series onto one x axis", () => {
    const { names, data } = alignSeries({ kind: "echo", series: { face: [[0, 1], [10, 2]], neck: [[10, 3]] } });
    expect(names).toEqual(["face", "neck"]);
    expect(data).toEqual([[0, 10], [1, 2], [null, 3]]);
  });
});

describe("visibleRows", () => {
  const row = (ms: number): SessionSummary => ({
    session_id: `s${ms}`, created_at_ms: ms, product: "savings_account", attempt: 1, state: "done", mode: null, outcome: null, label_kind: null,
  });
  const rows = [row(500), row(1000), row(1500)];

  it("returns all rows when cutoff is null", () => {
    expect(visibleRows(rows, null)).toHaveLength(3);
  });

  it("keeps only rows strictly newer than the cutoff", () => {
    expect(visibleRows(rows, 1000)).toEqual([row(1500)]);
  });
});

describe("ConsoleList reset demo", () => {
  const row = (id: string, ms: number): SessionSummary => ({
    session_id: id, created_at_ms: ms, product: "savings_account", attempt: 1, state: "done", mode: null, outcome: null, label_kind: null,
  });

  beforeEach(() => {
    localStorage.clear();
    sessionStorage.setItem("pulselens.agent_passcode", "pc");
    api.listSessions.mockResolvedValue([row("old1", 1000), row("old2", 2000)]);
  });

  it("reset hides existing rows, show all brings them back", async () => {
    at("/console");
    await screen.findByRole("table", { name: "Sessions" });
    fireEvent.click(screen.getByRole("button", { name: "Reset demo" }));
    expect(await screen.findByText("No sessions yet.")).toBeTruthy();
    expect(localStorage.getItem("pulselens.reset_after_ms")).toBe("2000");
    fireEvent.click(screen.getByRole("button", { name: "Show all" }));
    const table = await screen.findByRole("table", { name: "Sessions" });
    expect(within(table).getByRole("link", { name: "old1" })).toBeTruthy();
    expect(within(table).getByRole("link", { name: "old2" })).toBeTruthy();
    expect(localStorage.getItem("pulselens.reset_after_ms")).toBeNull();
  });

  it("reset survives a re-render", async () => {
    const first = at("/console");
    await screen.findByRole("table", { name: "Sessions" });
    fireEvent.click(screen.getByRole("button", { name: "Reset demo" }));
    expect(await screen.findByText("No sessions yet.")).toBeTruthy();
    first.unmount();
    at("/console");
    expect(await screen.findByText("No sessions yet.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Show all" })).toBeTruthy();
  });
});
