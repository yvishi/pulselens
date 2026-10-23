import { afterEach, describe, expect, it, vi } from "vitest";
import { now } from "./clock";
import { isoluminantColour } from "./colour";
import { LightOverlay, viewportHeight } from "./overlay";

let overlay: LightOverlay | null = null;
afterEach(() => {
  overlay?.dispose();
  vi.unstubAllGlobals();
});

describe("LightOverlay", () => {
  it("paints full-screen and reports times since t0", async () => {
    const t0 = now();
    overlay = new LightOverlay(document.body, "fullscreen", { t0 });
    const grey = overlay.element.style.background;
    const painted = await overlay.paint(isoluminantColour(200));
    expect(painted).toBeGreaterThanOrEqual(0);
    expect(painted).toBeLessThan(now() - t0 + 1);
    expect(overlay.element.style.background).not.toBe(grey);
    const ended = await overlay.clear();
    expect(ended).toBeGreaterThanOrEqual(painted);
    expect(overlay.element.style.background).toBe(grey);
  });

  it("falls back to a border of 18% of the short side", async () => {
    overlay = new LightOverlay(document.body, "border");
    await overlay.paint(isoluminantColour(80));
    expect(overlay.element.style.borderWidth).toBe(`${Math.round(0.18 * Math.min(innerWidth, innerHeight))}px`);
    expect(overlay.element.style.background).toBe("");
  });

  it("shows prompts as white text on a dark 50% backdrop", () => {
    overlay = new LightOverlay(document.body, "fullscreen");
    overlay.showPrompt("Turn to your left");
    expect(overlay.prompt.textContent).toBe("Turn to your left");
    expect(overlay.prompt.style.color).toBe("rgb(255, 255, 255)");
    expect(overlay.prompt.style.background).toBe("rgba(0, 0, 0, 0.5)");
    overlay.dispose();
    expect(document.body.contains(overlay.element)).toBe(false);
  });

  it("covers the whole dynamic viewport in fullscreen mode (iPhone has no Fullscreen API)", () => {
    vi.stubGlobal("CSS", { supports: (p: string, v: string) => p === "height" && v === "100dvh" });
    overlay = new LightOverlay(document.body, "fullscreen");
    const s = overlay.element.style;
    expect(s.position).toBe("fixed");
    expect([s.top, s.left, s.right]).toEqual(["0px", "0px", "0px"]);
    expect(s.width).toBe("100%");
    expect(s.height).toBe("100dvh");
  });

  it("falls back to 100vh where dvh is unknown", () => {
    vi.stubGlobal("CSS", { supports: () => false });
    expect(viewportHeight()).toBe("100vh");
    vi.stubGlobal("CSS", undefined);
    expect(viewportHeight()).toBe("100vh");
  });

  it("leaves the border mode's box to inset: 0", () => {
    overlay = new LightOverlay(document.body, "border");
    expect(overlay.element.style.height).toBe("");
  });
});
