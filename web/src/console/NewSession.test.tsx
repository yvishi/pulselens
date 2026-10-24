import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useParams } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({ createSession: vi.fn() }));
vi.mock("../api/client", () => api);
vi.mock("qrcode", () => ({ default: { toCanvas: vi.fn().mockResolvedValue(undefined) } }));

const { default: QRCode } = await import("qrcode");
const { NewSession, CustomerLink, customerLink } = await import("./NewSession");

function SessionPage() {
  return <p>Session page {useParams().sessionId}</p>;
}

function renderNew() {
  return render(
    <MemoryRouter initialEntries={["/console"]}>
      <Routes>
        <Route path="/console" element={<NewSession />} />
        <Route path="/console/:sessionId" element={<SessionPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

function stubClipboard(writeText = vi.fn().mockResolvedValue(undefined)) {
  Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
  return writeText;
}

describe("customerLink", () => {
  it("joins origin and customer_url", () => {
    expect(customerLink("https://x.trycloudflare.com", "/customer/ab?t=1")).toBe("https://x.trycloudflare.com/customer/ab?t=1");
  });
});

describe("NewSession", () => {
  beforeEach(() => {
    api.createSession.mockReset();
    vi.mocked(QRCode.toCanvas).mockClear();
  });
  afterEach(cleanup);

  it("sends the chosen product and no_flash", async () => {
    api.createSession.mockResolvedValue({ session_id: "s1", customer_url: "/customer/s1?t=1" });
    renderNew();
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "instant_loan" } });
    fireEvent.click(screen.getByLabelText("No flash"));
    fireEvent.click(screen.getByRole("button", { name: "New session" }));
    await waitFor(() => expect(api.createSession).toHaveBeenCalledWith({ product: "instant_loan", no_flash: true }));
  });

  it("explains the no-flash option in plain words", () => {
    renderNew();
    expect(screen.getByLabelText("No flash").getAttribute("aria-describedby")).toBeTruthy();
    expect(screen.getByText(/sensitive to flashing light/)).toBeTruthy();
  });

  it("shows the link, draws a QR and copies the link with feedback", async () => {
    api.createSession.mockResolvedValue({ session_id: "s1", customer_url: "/customer/s1?t=1" });
    const writeText = stubClipboard();
    const { container } = renderNew();
    fireEvent.click(screen.getByRole("button", { name: "New session" }));
    const region = screen.getByRole("region", { name: "New session" });
    const link = await within(region).findByRole("link");
    expect(link.textContent).toContain("/customer/");
    const text = link.textContent as string;
    expect(link.getAttribute("href")).toBe(text);
    expect(screen.getByText(/Ask the customer to open this link on their phone/)).toBeTruthy();
    const canvas = container.querySelector("canvas");
    expect(canvas).not.toBeNull();
    await waitFor(() => expect(QRCode.toCanvas).toHaveBeenCalledWith(canvas, text, { width: 256 }));
    fireEvent.click(screen.getByRole("button", { name: "Copy link" }));
    expect(writeText).toHaveBeenCalledWith(text);
    expect(await screen.findByRole("button", { name: "Copied" })).toBeTruthy();
  });

  it("says so when the link cannot be copied", async () => {
    stubClipboard(vi.fn().mockRejectedValue(new Error("denied")));
    render(<CustomerLink url="https://x/customer/s1?t=1" />);
    fireEvent.click(screen.getByRole("button", { name: "Copy link" }));
    expect(await screen.findByText(/Could not copy/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Copy link" })).toBeTruthy();
  });

  it("opens the new verification from 'Watch this verification'", async () => {
    api.createSession.mockResolvedValue({ session_id: "abc123", customer_url: "/customer/abc123?t=1" });
    renderNew();
    fireEvent.click(screen.getByRole("button", { name: "New session" }));
    fireEvent.click(await screen.findByRole("button", { name: "Watch this verification" }));
    expect(await screen.findByText("Session page abc123")).toBeTruthy();
  });

  it("shows the error and keeps the button enabled", async () => {
    api.createSession.mockRejectedValue(new Error("boom"));
    renderNew();
    fireEvent.click(screen.getByRole("button", { name: "New session" }));
    expect((await screen.findByRole("alert")).textContent).toContain("boom");
    expect(screen.getByRole("button", { name: "New session" })).toHaveProperty("disabled", false);
  });
});
