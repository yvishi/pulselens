import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { API, DATA, WEB, createSession } from "./support/bundle";

// K7: the agent console against the real server with PULSE_FAKE_ANALYSIS=1 (see playwright.config.ts).
const PASSCODE = "e2e-passcode";
const JPEG = Buffer.from([0xff, 0xd8, 0xff, 0xd9]);
const PREFLIGHT = {
  user_agent: "e2e", platform: "desktop", browser: "Brave", camera_label: "fake", width: 640, height: 480,
  measured_fps: 30, dropped_frame_ratio: 0, blur: 100, brightness: 120, face_found: true, face_fraction: 0.1,
  controls: [], gyro: false, no_flash_requested: false, clock: "now", probe: [],
};

/** A minimal finished session through the customer API: preflight, challenge, 60 frames, events, complete. */
async function completedSession(request: APIRequestContext): Promise<string> {
  const created = await createSession(request);
  const id: string = created.session_id;
  const auth = { Authorization: `Bearer ${created.customer_token}` };
  expect((await request.post(`${API}/api/sessions/${id}/preflight`, { headers: auth, data: PREFLIGHT })).ok()).toBe(true);
  const challenge = await (await request.get(`${API}/api/sessions/${id}/challenge`, { headers: auth })).json();
  for (let seq = 0; seq < 2; seq++) {
    const frames = Array.from({ length: 30 }, (_, k) => ({ idx: seq * 30 + k, t_ms: (seq * 30 + k) * 33.3, w: 640, h: 480 }));
    const multipart: Record<string, string | { name: string; mimeType: string; buffer: Buffer }> = {
      meta: JSON.stringify({ batch_seq: seq, frames }),
    };
    for (const f of frames) multipart[`f${f.idx}`] = { name: `${f.idx}.jpg`, mimeType: "image/jpeg", buffer: JPEG };
    expect((await request.post(`${API}/api/sessions/${id}/frames`, { headers: auth, multipart })).status()).toBe(204);
  }
  const events = challenge.steps.map((s: { step_id: string; start_offset_ms: number; kind: string }) => ({
    step_id: s.step_id, status: "shown", painted_t_ms: challenge.baseline_ms + s.start_offset_ms + 5,
    ended_t_ms: null, shown_rgb: s.kind === "colour" ? [0.6, 0.5, 0.3] : null,
  }));
  expect((await request.post(`${API}/api/sessions/${id}/events`, { headers: auth, data: events })).status()).toBe(204);
  expect((await request.post(`${API}/api/sessions/${id}/complete`, { headers: auth })).status()).toBe(202);
  return id;
}

async function signIn(page: Page, url: string) {
  await page.goto(url);
  await page.getByLabel("Agent passcode").fill(PASSCODE);
  await page.getByRole("button", { name: "Open console" }).click();
}

test("home loads and the server is reachable through the proxy", async ({ page, request }) => {
  await page.goto(`${WEB}/`);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("PulseLens");
  const health = await request.get(`${WEB}/api/health`);
  expect(await health.json()).toEqual({ ok: true });
});

test("passcode required: no data without it, and a wrong one is refused", async ({ page, request }) => {
  expect((await request.get(`${API}/api/sessions`)).status()).toBe(401);
  await page.goto(`${WEB}/console`);
  await expect(page.getByRole("table", { name: "Sessions" })).toHaveCount(0);
  await page.getByLabel("Agent passcode").fill("wrong");
  await page.getByRole("button", { name: "Open console" }).click();
  await expect(page.getByRole("alert")).toContainText("not accepted");
});

test("a session reaches its decision, labelled FAKE ANALYSIS", async ({ page, request }) => {
  const id = await completedSession(request);
  await signIn(page, `${WEB}/console`);
  await page.getByRole("link", { name: id }).click();
  const banner = page.getByRole("region", { name: "Outcome" });
  await expect(banner).toContainText("PASS", { timeout: 10_000 });
  await expect(banner).toContainText("PulseLens recommends; the agent decides.");
  await expect(page.getByText("FAKE ANALYSIS", { exact: true })).toBeVisible();
  await expect(page.getByText("PROVISIONAL THRESHOLDS")).toBeVisible();
  await expect(page.getByRole("region", { name: "Challenge timeline" })).toBeVisible();
});

for (const size of [{ width: 1920, height: 1080 }, { width: 1366, height: 768 }]) {
  test(`no overflow at ${size.width}x${size.height}`, async ({ page, request }) => {
    const id = await completedSession(request);
    await page.setViewportSize(size);
    await signIn(page, `${WEB}/console/${id}`);
    await expect(page.getByRole("region", { name: "Outcome" })).toContainText("PASS", { timeout: 10_000 });
    for (const details of await page.locator("details.check").all()) await details.evaluate((d) => ((d as HTMLDetailsElement).open = true));
    const overflowing = await page.evaluate(() =>
      [...document.querySelectorAll("main *")].filter((el) => el.scrollWidth > el.clientWidth + 1 && getComputedStyle(el).overflowX === "visible")
        .map((el) => `${el.tagName}.${el.className}`),
    );
    expect(overflowing).toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  });
}

test("an agent action is recorded and shows after a reload", async ({ page, request }) => {
  const id = await completedSession(request);
  await signIn(page, `${WEB}/console/${id}`);
  await expect(page.getByRole("region", { name: "Outcome" })).toContainText("PASS", { timeout: 10_000 });
  await page.getByLabel("Note").fill("documents match");
  await page.getByRole("button", { name: "Approve" }).click();
  await expect(page.getByRole("status")).toContainText("Approved");
  const agentFile = path.join(DATA, id, "agent.json");
  await expect.poll(() => existsSync(agentFile)).toBe(true);
  expect(JSON.parse(readFileSync(agentFile, "utf8"))).toMatchObject({ action: "approve", note: "documents match" });
  await page.reload();
  await expect(page.getByRole("status")).toHaveText(/^Approved at .+: "documents match"$/);
  await expect(page.getByRole("button", { name: "Approve" })).toBeDisabled(); // final: clickable once
});

test("new session shows a QR code and a customer link", async ({ page }) => {
  await signIn(page, `${WEB}/console`);
  await page.getByRole("button", { name: "New session" }).click();
  const section = page.getByRole("region", { name: "New session" });
  await expect(section.getByRole("link")).toContainText("/customer/");
  const canvas = section.locator("canvas");
  await expect(canvas).toBeVisible();
  expect(await canvas.evaluate((c: HTMLCanvasElement) => c.width)).toBeGreaterThanOrEqual(240);
});
