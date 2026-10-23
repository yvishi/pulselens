import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({ createSession: vi.fn() }));
vi.mock("../api/client", () => api);
vi.mock("qrcode", () => ({ default: { toCanvas: vi.fn().mockResolvedValue(undefined) } }));

const { default: QRCode } = await import("qrcode");
const { NewSession, customerLink } = await import("./NewSession");

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
    render(<NewSession />);
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "instant_loan" } });
    fireEvent.click(screen.getByLabelText("No flash"));
    fireEvent.click(screen.getByRole("button", { name: "New session" }));
    await waitFor(() => expect(api.createSession).toHaveBeenCalledWith({ product: "instant_loan", no_flash: true }));
  });

  it("shows the link, draws a QR and copies the link", async () => {
    api.createSession.mockResolvedValue({ session_id: "s1", customer_url: "/customer/s1?t=1" });
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    const { container } = render(<NewSession />);
    fireEvent.click(screen.getByRole("button", { name: "New session" }));
    const link = await screen.findByRole("link");
    expect(link.textContent).toContain("/customer/");
    const text = link.textContent as string;
    const canvas = container.querySelector("canvas");
    expect(canvas).not.toBeNull();
    await waitFor(() => expect(QRCode.toCanvas).toHaveBeenCalledWith(canvas, text, { width: 256 }));
    fireEvent.click(screen.getByRole("button", { name: "Copy link" }));
    expect(writeText).toHaveBeenCalledWith(text);
  });

  it("shows the error and keeps the button enabled", async () => {
    api.createSession.mockRejectedValue(new Error("boom"));
    render(<NewSession />);
    fireEvent.click(screen.getByRole("button", { name: "New session" }));
    expect((await screen.findByRole("alert")).textContent).toContain("boom");
    expect(screen.getByRole("button", { name: "New session" })).toHaveProperty("disabled", false);
  });
});
