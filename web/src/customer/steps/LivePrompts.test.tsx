import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { now } from "../../capture/clock";
import { textDigitPrompt, textNodPrompt, type LivePromptContext } from "../../capture/livePrompts";
import { cardDigitPrompt, cardNodPrompt } from "./LivePrompts";

function context(): LivePromptContext & { prompts: (string | null)[] } {
  const prompts: (string | null)[] = [];
  return {
    prompts,
    overlay: { t0: now(), showPrompt: (s) => prompts.push(s) },
    video: document.createElement("video"),
    nodText: () => "Nod your head: down, then back up",
    digitText: () => "Say this number out loud",
  };
}

beforeEach(() => vi.useFakeTimers());
afterEach(() => {
  vi.useRealTimers();
  document.body.innerHTML = "";
});

describe("card prompts", () => {
  it("the nod shows its card with the self-view raised, for duration_ms, then removes both", async () => {
    const ctx = context();
    const p = cardNodPrompt()(ctx)(2500);
    await vi.advanceTimersByTimeAsync(100);
    const host = document.querySelector<HTMLElement>("[data-nod-prompt]")!;
    expect(host.textContent).toContain("Nod your head: down, then back up");
    expect(ctx.video.style.zIndex).not.toBe("");
    await vi.advanceTimersByTimeAsync(2600);
    const { painted, ended } = await p;
    expect(ended - painted).toBeGreaterThanOrEqual(2500);
    expect(document.querySelector("[data-nod-prompt]")).toBeNull();
    expect(ctx.video.style.zIndex).toBe("");
  });

  it("a digit shows the number large, without the self-view, then removes it", async () => {
    const ctx = context();
    const p = cardDigitPrompt()(ctx)(7, 1200);
    await vi.advanceTimersByTimeAsync(100);
    const host = document.querySelector<HTMLElement>("[data-digit-prompt]")!;
    expect(host.dataset.digitPrompt).toBe("7");
    expect(host.querySelector("[data-digit]")!.textContent).toBe("7");
    expect(host.textContent).toContain("Say this number out loud");
    expect(ctx.video.style.zIndex).toBe("");
    await vi.advanceTimersByTimeAsync(1300);
    const { painted, ended } = await p;
    expect(ended - painted).toBeGreaterThanOrEqual(1200);
    expect(document.querySelector("[data-digit-prompt]")).toBeNull();
  });
});

describe("text prompts (fallback)", () => {
  it("write the nod and the digit on the overlay and clear them", async () => {
    const ctx = context();
    const nod = textNodPrompt(ctx)(500);
    await vi.advanceTimersByTimeAsync(600);
    await nod;
    const digit = textDigitPrompt(ctx)(4, 500);
    await vi.advanceTimersByTimeAsync(600);
    await digit;
    expect(ctx.prompts).toEqual(["↕ Nod your head: down, then back up", null, "Say this number out loud: 4", null]);
  });
});
