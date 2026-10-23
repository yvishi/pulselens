import { afterEach, describe, expect, it } from "vitest";
import { now } from "./clock";
import { isoluminantColour } from "./colour";
import { LightOverlay } from "./overlay";

let overlay: LightOverlay | null = null;
afterEach(() => overlay?.dispose());

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
});
