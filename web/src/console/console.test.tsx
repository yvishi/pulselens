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
const { ConsoleList, matchesFilter, visibleRows } = await import("./ConsoleList");
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

  it("flags an escalated session and takes closed ones out of Needs attention", async () => {
    const base: SessionSummary = {
      session_id: "esc", created_at_ms: 0, product: "savings_account", attempt: 1, state: "done", mode: "CAPABLE",
      outcome: "HUMAN_REVIEW", label_kind: null, agent_action: "escalate",
    };
    expect(matchesFilter(base, "attention")).toBe(false);
    expect(matchesFilter({ ...base, agent_action: "approve" }, "attention")).toBe(false);
    expect(matchesFilter({ ...base, agent_action: "reverify" }, "attention")).toBe(true);
    expect(matchesFilter({ ...base, agent_action: null }, "attention")).toBe(true);
    api.listSessions.mockResolvedValue([base]);
    at("/console");
    enterPasscode("secret");
    fireEvent.click(await screen.findByRole("button", { name: /^All/ }));
    const table = await screen.findByRole("table", { name: "Sessions" });
    expect(table.textContent).toContain("Flagged for fraud");
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
  beforeEach(() => {
    sessionStorage.setItem("pulselens.agent_passcode", "pc");
    api.listSessions.mockResolvedValue([]);
  });

  it("shows the outcome, honesty labels, plan reasons and families with failed and abstained apart", async () => {
    api.getResult.mockResolvedValue(REPORT);
    at("/console/d79105c5121a3cb3");
    const banner = await screen.findByRole("region", { name: "Outcome" });
    expect(banner.textContent).toContain("HUMAN REVIEW");
    expect(within(banner).getByRole("heading", { level: 2 }).textContent).toBe("Needs your review");
    expect(banner.textContent).toContain("What to do next");
    expect(banner.textContent).toContain("PulseLens recommends; the agent decides.");
    expect(screen.getByText("PROVISIONAL THRESHOLDS")).toBeTruthy();
    expect(screen.getByText("FAKE ANALYSIS")).toBeTruthy();
    expect(screen.getByText(/fewer frames than a full challenge needs/)).toBeTruthy();
    const b = screen.getByRole("region", { name: "Family B: Sensor and stream" });
    expect(within(b).getByText("Problem found")).toBeTruthy();
    expect(within(b).getByText("Raised risk").parentElement!.textContent).toContain("72.4%");
    expect(within(b).getByText("Checked, no risk").parentElement!.textContent).toContain("FAKE ANALYSIS");
    const d = screen.getByRole("region", { name: "Family D: Visual and motion" });
    expect(within(d).getByText("Couldn't tell")).toBeTruthy();
    expect(within(d).getByText("Could not judge").parentElement!.textContent).toContain("lost during the turn");
    expect(within(d).queryByText("Raised risk")).toBeNull();
    const a = screen.getByRole("region", { name: "Family A: Pulse" });
    expect(a.textContent).toContain("not used in the decision");
    const timeline = screen.getByRole("region", { name: "Challenge timeline" });
    expect(timeline.textContent).toContain("1 skipped");
    expect(timeline.textContent).toContain("the camera slowed down");
    const checked = screen.getByRole("region", { name: "What PulseLens checked" });
    expect(checked.textContent).toContain("Is it a real, live camera?");
    expect(checked.textContent).toContain("Not checked");
  });

  it("shows the step-up in plain words and suggests the matching action", async () => {
    api.getResult.mockResolvedValue({ ...REPORT, decision: { ...DECISION, outcome: "RETRY_STEP_UP", step_up: "no_flash" } });
    at("/console/d79105c5121a3cb3");
    const banner = await screen.findByRole("region", { name: "Outcome" });
    expect(banner.textContent).toContain("Try again");
    expect(banner.textContent).toContain("Send a new link without flashing light.");
    expect(banner.textContent).toContain("RETRY / STEP-UP");
    const reverify = screen.getByRole("button", { name: "Re-verify" });
    expect(reverify.closest(".choice")!.className).toContain("is-suggested");
    expect(screen.getByRole("button", { name: "Approve" }).closest(".choice")!.className).not.toContain("is-suggested");
  });

  it("on PASS says no signs of a fake, never that the customer is genuine", async () => {
    api.getResult.mockResolvedValue({ ...REPORT, decision: { ...DECISION, outcome: "PASS", reasons: [] } });
    at("/console/d79105c5121a3cb3");
    const banner = await screen.findByRole("region", { name: "Outcome" });
    expect(within(banner).getByRole("heading", { level: 2 }).textContent).toBe("No signs of a fake found");
    expect(banner.textContent).toContain("Nothing raised risk.");
    const decide = screen.getByRole("region", { name: "Your decision" });
    expect(`${banner.textContent} ${decide.textContent}`).not.toMatch(/genuine/i);
  });

  it("links to the newer and older sessions, from one fetch of the list", async () => {
    const row = (id: string, ms: number): SessionSummary => ({
      session_id: id, created_at_ms: ms, product: "savings_account", attempt: 1, state: "done", mode: null, outcome: null, label_kind: null,
    });
    api.listSessions.mockResolvedValue([row("older1", 1000), row("d79105c5121a3cb3", 2000), row("newer1", 3000)]);
    api.getResult.mockResolvedValue(REPORT);
    at("/console/d79105c5121a3cb3");
    expect((await screen.findByRole("link", { name: /Newer session/ })).getAttribute("href")).toBe("/console/newer1");
    expect(screen.getByRole("link", { name: /Older session/ }).getAttribute("href")).toBe("/console/older1");
    expect(screen.getByRole("link", { name: "Verifications" }).getAttribute("href")).toBe("/console");
    expect(api.listSessions).toHaveBeenCalledTimes(1);
  });

  it("disables newer when this is the newest session", async () => {
    api.listSessions.mockResolvedValue([
      { session_id: "d79105c5121a3cb3", created_at_ms: 2000, product: "savings_account", attempt: 1, state: "done", mode: null, outcome: null, label_kind: null },
      { session_id: "older1", created_at_ms: 1000, product: "savings_account", attempt: 1, state: "done", mode: null, outcome: null, label_kind: null },
    ]);
    api.getResult.mockResolvedValue(REPORT);
    at("/console/d79105c5121a3cb3");
    await screen.findByRole("link", { name: /Older session/ });
    expect(screen.queryByRole("link", { name: /Newer session/ })).toBeNull();
    expect(screen.getByText("← Newer session").getAttribute("aria-disabled")).toBe("true");
  });

  it("asks for confirmation before escalating to fraud", async () => {
    api.getResult.mockResolvedValue(REPORT);
    api.postAgentDecision.mockResolvedValue(undefined);
    at("/console/d79105c5121a3cb3");
    fireEvent.click(await screen.findByRole("button", { name: "Escalate to fraud" }));
    expect(api.postAgentDecision).not.toHaveBeenCalled();
    expect(screen.getByText("Escalate this customer to the fraud team?")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByText("Escalate this customer to the fraud team?")).toBeNull();
    expect(api.postAgentDecision).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Escalate to fraud" }));
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Confirm" })));
    expect(api.postAgentDecision).toHaveBeenCalledWith("d79105c5121a3cb3", "pc", { action: "escalate", note: "" });
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

  it("approve is clickable once: the buttons lock and the saved time shows", async () => {
    const saved = { action: "approve" as const, note: "", at_ms: Date.UTC(2026, 9, 25, 9, 30) };
    api.getResult.mockResolvedValueOnce(REPORT).mockResolvedValue({ ...REPORT, agent_decision: saved });
    api.postAgentDecision.mockResolvedValue(undefined);
    at("/console/d79105c5121a3cb3");
    const approve = await screen.findByRole("button", { name: "Approve" });
    await act(async () => fireEvent.click(approve));
    fireEvent.click(approve);
    expect(api.postAgentDecision).toHaveBeenCalledTimes(1);
    const time = new Date(saved.at_ms).toLocaleTimeString();
    await waitFor(() => expect(screen.getByRole("status").textContent).toBe(`Approved at ${time}`));
    for (const name of ["Approve", "Re-verify", "Escalate to fraud"]) {
      expect((screen.getByRole("button", { name }) as HTMLButtonElement).disabled).toBe(true);
    }
    expect(screen.getByText(/This decision is final/)).toBeTruthy();
  });

  it("an escalated session is flagged and every button is locked", async () => {
    api.getResult.mockResolvedValue({ ...REPORT, agent_decision: { action: "escalate", note: "", at_ms: 1 } });
    at("/console/d79105c5121a3cb3");
    const escalate = await screen.findByRole("button", { name: "Escalate to fraud" });
    expect((escalate as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole("button", { name: "Approve" }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getAllByText("Flagged for fraud").length).toBe(2); // the page header and the decision panel
    expect(screen.getByRole("status").textContent).toMatch(/^Escalated to fraud at /);
  });

  it("says so when the server has already recorded a final decision", async () => {
    api.getResult.mockResolvedValue(REPORT);
    api.postAgentDecision.mockRejectedValue(new ApiError(409, "already_decided"));
    at("/console/d79105c5121a3cb3");
    const approve = await screen.findByRole("button", { name: "Approve" });
    await act(async () => fireEvent.click(approve));
    expect((await screen.findByRole("alert")).textContent).toMatch(/already decided/);
  });

  describe("live questions card", () => {
    const CARD = "Live questions to ask";

    it("shows when the plan has agent questions", async () => {
      api.getResult.mockResolvedValue({ ...REPORT, plan: { ...REPORT.plan!, agent_questions: true } });
      at("/console/d79105c5121a3cb3");
      expect(await screen.findByRole("heading", { name: CARD })).toBeTruthy();
      expect(screen.getAllByRole("checkbox")).toHaveLength(3);
    });

    it("shows for the agent_checks step-up", async () => {
      api.getResult.mockResolvedValue({ ...REPORT, decision: { ...DECISION, outcome: "RETRY_STEP_UP", step_up: "agent_checks" } });
      at("/console/d79105c5121a3cb3");
      expect(await screen.findByRole("heading", { name: CARD })).toBeTruthy();
    });

    it("is absent otherwise", async () => {
      api.getResult.mockResolvedValue(REPORT);
      at("/console/d79105c5121a3cb3");
      await screen.findByRole("region", { name: "Your decision" });
      expect(screen.queryByRole("heading", { name: CARD })).toBeNull();
    });

    it("is hidden once the agent has decided (the ticks live in the saved note)", async () => {
      api.getResult.mockResolvedValue({
        ...REPORT, plan: { ...REPORT.plan!, agent_questions: true }, agent_decision: { action: "approve", note: "Live checks: x done" },
      });
      at("/console/d79105c5121a3cb3");
      await screen.findByRole("region", { name: "Your decision" });
      expect(screen.queryByRole("heading", { name: CARD })).toBeNull();
    });

    it("saves the ticks with the decision note", async () => {
      api.getResult.mockResolvedValue({ ...REPORT, plan: { ...REPORT.plan!, agent_questions: true } });
      api.postAgentDecision.mockResolvedValue(undefined);
      at("/console/d79105c5121a3cb3");
      const boxes = await screen.findAllByRole("checkbox");
      fireEvent.click(boxes[0]!);
      fireEvent.change(screen.getByLabelText("Note"), { target: { value: "ok" } });
      await act(async () => fireEvent.click(screen.getByRole("button", { name: "Approve" })));
      const note = api.postAgentDecision.mock.calls[0]![2].note as string;
      expect(note.startsWith("ok\nLive checks: ")).toBe(true);
      expect(note).toContain(" done; ");
    });
  });

  it("re-verify creates the next attempt and shows its customer link", async () => {
    api.getResult.mockResolvedValue(REPORT);
    api.postAgentDecision.mockResolvedValue(undefined);
    api.createSession.mockResolvedValue({ session_id: "next", customer_url: "/customer/next?t=tok" });
    const { container } = at("/console/d79105c5121a3cb3");
    const reverify = await screen.findByRole("button", { name: "Re-verify" });
    await act(async () => fireEvent.click(reverify));
    expect(api.createSession).toHaveBeenCalledWith({ product: "instant_loan", previous_session_id: "d79105c5121a3cb3", no_flash: false });
    expect((await screen.findByRole("link", { name: /customer\/next/ })).getAttribute("href")).toContain("/customer/next?t=tok");
    expect(container.querySelector(".next-link canvas")).not.toBeNull();
    expect(screen.getByRole("button", { name: "Copy link" })).toBeTruthy();
    expect(screen.getByText("New link for the customer")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Watch the new attempt" }).getAttribute("href")).toBe("/console/next");
  });

  it("re-verify after a no_flash step-up asks for a no-flash attempt", async () => {
    api.getResult.mockResolvedValue({ ...REPORT, decision: { ...DECISION, outcome: "RETRY_STEP_UP", step_up: "no_flash" } });
    api.postAgentDecision.mockResolvedValue(undefined);
    api.createSession.mockResolvedValue({ session_id: "next", customer_url: "/customer/next?t=tok" });
    at("/console/d79105c5121a3cb3");
    const reverify = await screen.findByRole("button", { name: "Re-verify" });
    await act(async () => fireEvent.click(reverify));
    expect(api.createSession).toHaveBeenCalledWith({ product: "instant_loan", previous_session_id: "d79105c5121a3cb3", no_flash: true });
  });

  it("re-verify keeps the customer's own no-flash choice", async () => {
    api.getResult.mockResolvedValue({ ...REPORT, preflight: { ...REPORT.preflight!, no_flash_requested: true } });
    api.postAgentDecision.mockResolvedValue(undefined);
    api.createSession.mockResolvedValue({ session_id: "next", customer_url: "/customer/next?t=tok" });
    at("/console/d79105c5121a3cb3");
    const reverify = await screen.findByRole("button", { name: "Re-verify" });
    await act(async () => fireEvent.click(reverify));
    expect(api.createSession).toHaveBeenCalledWith({ product: "instant_loan", previous_session_id: "d79105c5121a3cb3", no_flash: true });
  });

  it("assisted_kyc step-up shows the bank process and suggests no button", async () => {
    api.getResult.mockResolvedValue({ ...REPORT, decision: { ...DECISION, outcome: "RETRY_STEP_UP", step_up: "assisted_kyc" } });
    const { container } = at("/console/d79105c5121a3cb3");
    const banner = await screen.findByRole("region", { name: "Outcome" });
    expect(banner.textContent).toContain("Follow the bank's assisted-KYC process (branch or business correspondent).");
    expect(container.querySelector(".choice.is-suggested")).toBeNull();
  });

  it("agent_checks step-up suggests no button and no new link", async () => {
    api.getResult.mockResolvedValue({ ...REPORT, decision: { ...DECISION, outcome: "RETRY_STEP_UP", step_up: "agent_checks" } });
    const { container } = at("/console/d79105c5121a3cb3");
    const banner = await screen.findByRole("region", { name: "Outcome" });
    expect(container.querySelector(".choice.is-suggested")).toBeNull();
    expect(within(banner).getByText(/What to do next/).nextElementSibling!.textContent).not.toMatch(/new link/);
  });

  it("keeps the actions closed until a decision exists", async () => {
    api.getResult.mockResolvedValue({ ...REPORT, decision: null, state: "analysing" });
    at("/console/d79105c5121a3cb3");
    expect((await screen.findByRole("button", { name: "Approve" })).hasAttribute("disabled")).toBe(true);
    expect(screen.getByRole("region", { name: "Outcome" }).textContent).toContain("Analysing");
    expect(screen.getByText("You can decide once the analysis has finished.")).toBeTruthy();
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
