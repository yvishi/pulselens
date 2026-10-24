import { chromium, expect, test, type Page } from "@playwright/test";
import { FORBIDDEN_WORDS, WEB, createSession, readBundle } from "./support/bundle";
import { REPLAY_API, REPLAY_Y4M, bundleToY4m, startRealServer, stopServer, waitForReport } from "./support/replay";

// Y4: the customer flow in Brave's fake camera, against the real server with PULSE_FAKE_ANALYSIS=1 and
// PULSE_DATA_DIR=data/e2e (both set by playwright.config.ts).
const CONTINUE = "Thank you, you can continue the call.";
const NO_FLASH = "I'd rather not see flashing colours";

// The fake camera has no face, so "Move closer" fires: 3 coaching rounds of 3 s plus a second preflight come
// before the challenge (a real user with no face found should get that tip too). Hence the generous waits.
test.describe.configure({ timeout: 150_000 });
const RESULT_WAIT_MS = 90_000;

/** Records every customer phase the page shows, and whether the page could scroll sideways in it. */
async function recordPhases(page: Page) {
  await page.addInitScript(() => {
    const log: { phase: string; overflow: boolean }[] = [];
    (window as unknown as { __phases: typeof log }).__phases = log;
    setInterval(() => {
      const phase = document.querySelector("main.customer")?.getAttribute("data-phase");
      if (!phase) return;
      const overflow = document.documentElement.scrollWidth > window.innerWidth;
      const last = log.at(-1);
      if (!last || last.phase !== phase || (overflow && !last.overflow)) log.push({ phase, overflow });
    }, 50);
  });
  return () => page.evaluate(() => (window as unknown as { __phases: { phase: string; overflow: boolean }[] }).__phases);
}

async function runFlow(page: Page, button: string) {
  const created = await createSession(page.request);
  await page.goto(`${WEB}${created.customer_url}`);
  await page.getByRole("button", { name: button, exact: true }).click();
  await expect(page.getByText(CONTINUE)).toBeVisible({ timeout: RESULT_WAIT_MS });
  return created.session_id;
}

test("full flow reaches result", async ({ page }) => {
  const id = await runFlow(page, "Start");
  const { challenge, frames, events } = readBundle(id);
  expect(frames.length).toBeGreaterThanOrEqual(100);
  const byIdx = [...frames].sort((a, b) => a.idx - b.idx);
  for (let k = 1; k < byIdx.length; k++) {
    expect(byIdx[k]!.idx).toBeGreaterThan(byIdx[k - 1]!.idx);
    expect(byIdx[k]!.t_ms).toBeGreaterThan(byIdx[k - 1]!.t_ms);
  }
  expect(challenge).not.toBeNull();
  expect(events.map((e) => e.step_id).sort()).toEqual(challenge!.steps.map((s) => s.step_id).sort());
});

test("no-flash path", async ({ page }) => {
  const id = await runFlow(page, NO_FLASH);
  const { plan, challenge, events } = readBundle(id);
  expect(plan?.mode).toBe("NO_FLASH");
  const colourSteps = new Set(challenge!.steps.filter((s) => s.kind === "colour").map((s) => s.step_id));
  expect(events.filter((e) => colourSteps.has(e.step_id) && e.status === "shown")).toEqual([]);
  expect(events.map((e) => e.step_id).sort()).toEqual(challenge!.steps.map((s) => s.step_id).sort());
});

test("no score leaks", async ({ page }) => {
  const bodies: { url: string; body: string }[] = [];
  const pending: Promise<void>[] = [];
  page.on("response", (r) => {
    if (!new URL(r.url()).pathname.startsWith("/api/")) return;
    pending.push(r.text().then((body) => void bodies.push({ url: r.url(), body }), () => undefined));
  });
  await runFlow(page, NO_FLASH);
  await Promise.all(pending);
  expect(bodies.some((b) => b.url.includes("/status"))).toBe(true);
  for (const { url, body } of bodies) {
    for (const word of FORBIDDEN_WORDS) expect(body, `${word} in ${url}`).not.toContain(word);
  }
  const text = await page.locator("main").innerText();
  for (const word of FORBIDDEN_WORDS) expect(text, word).not.toContain(word);
});

test("360px no sideways scroll on every customer phase", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 740 });
  const phases = await recordPhases(page);
  await runFlow(page, "Start");
  await page.waitForTimeout(200);
  const seen = await phases();
  const names = new Set(seen.map((p) => p.phase));
  for (const phase of ["consent", "preflight", "challenge", "result"]) expect(names).toContain(phase);
  expect(names.has("uploading") || names.has("waiting")).toBe(true);
  expect(seen.filter((p) => p.overflow)).toEqual([]);

  // The error screen (a link without its token) too.
  const created = await createSession(page.request);
  await page.goto(`${WEB}/customer/${created.session_id}`);
  await expect(page.getByRole("alert")).toContainText("ask the agent for a new link");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

// Y10: the replay attack. A genuine recorded session (REPLAY_SESSION_DIR, e.g. data/sessions/<id> from /lab) is played
// back as the camera; it cannot answer this session's colours, so real analysis must not PASS it. Opt-in only:
//   REPLAY_SESSION_DIR=... npx playwright test --grep @real-analysis
// Without REPLAY_SESSION_DIR it skips, so the default run is unaffected.
test("@real-analysis replay is not PASS", async ({ request }, testInfo) => {
  const sessionDir = process.env.REPLAY_SESSION_DIR;
  test.skip(!sessionDir, "set REPLAY_SESSION_DIR to a genuine recorded session dir (data/sessions/<id>) to run it");
  test.setTimeout(420_000);
  const passcode = process.env.AGENT_PASSCODE ?? "e2e-passcode";
  const y4m = bundleToY4m(sessionDir!, REPLAY_Y4M);

  const server = await startRealServer(request, passcode);
  const { launchOptions, headless } = testInfo.project.use;
  const browser = await chromium.launch({
    executablePath: launchOptions?.executablePath,
    headless: headless ?? true,
    args: [
      "--use-fake-device-for-media-stream",
      "--use-fake-ui-for-media-stream",
      `--use-file-for-fake-video-capture=${y4m}`,
    ],
  });
  try {
    const context = await browser.newContext({ viewport: { width: 1280, height: 720 }, permissions: ["camera"] });
    const page = await context.newPage();
    // The app's /api calls go to the real-analysis server instead of the shared fake one on :8000.
    await page.route(`${WEB}/api/**`, (route) => route.continue({ url: route.request().url().replace(WEB, REPLAY_API) }));
    const created = await createSession(request, {}, REPLAY_API);
    await page.goto(`${WEB}${created.customer_url}`);
    await page.getByRole("button", { name: "Start", exact: true }).click();
    const main = page.locator("main.customer");
    await expect(main).toHaveAttribute("data-phase", /^(result|error)$/, { timeout: 180_000 });
    expect(await main.getAttribute("data-phase"), await main.innerText()).toBe("result");

    const report = await waitForReport(request, created.session_id, passcode);
    testInfo.annotations.push({
      type: "decision",
      description: `${report.decision!.outcome} ${report.decision!.step_up ?? ""}: ${report.decision!.reasons.join(" | ")}`,
    });
    expect(report.decision!.outcome).not.toBe("PASS");
  } finally {
    await browser.close();
    stopServer(server);
  }
});
