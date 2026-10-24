import { expect, test, type Page } from "@playwright/test";
import { FORBIDDEN_WORDS, WEB } from "./support/bundle";
import { readSessionFile } from "./support/sessionFile";

// Y8: the Lab recording page in Brave's fake camera, against the real server (PULSE_DATA_DIR=data/e2e).
// Coaching rounds run here too (the fake camera has no face), so the waits are generous; see customer.spec.ts.
test.describe.configure({ timeout: 150_000 });

const LABEL = {
  person: "P07", device: "D03", light: "dim", kind: "replay_screen", tool: "phone_screen", set: "B", consent_ref: "CF-E2E-1",
} as const;

async function fillForm(page: Page, consentRef: string) {
  await page.goto(`${WEB}/lab`);
  await page.getByLabel("Person code").fill(LABEL.person);
  await page.getByLabel("Device code").fill(LABEL.device);
  await page.getByLabel("Light").selectOption(LABEL.light);
  await page.getByLabel("Kind").selectOption(LABEL.kind);
  await page.getByLabel(/^Tool/).fill(LABEL.tool);
  await page.getByLabel("Set").selectOption(LABEL.set);
  await page.getByLabel("Consent reference").fill(consentRef);
}

test("a missing consent reference blocks Continue", async ({ page }) => {
  const created: string[] = [];
  page.on("request", (r) => {
    if (r.method() === "POST" && new URL(r.url()).pathname === "/api/sessions") created.push(r.url());
  });
  await fillForm(page, "");
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page.getByText("The consent reference is required.")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Hand the device to the person" })).toHaveCount(0);
  expect(created).toEqual([]);
});

test("a full recording writes session.json with the label", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 740 });
  await fillForm(page, LABEL.consent_ref);
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page.getByRole("heading", { name: "Hand the device to the person" })).toBeVisible();
  await page.getByRole("button", { name: "The person has the device" }).click();
  await page.getByRole("button", { name: "Start", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Recording saved" })).toBeVisible({ timeout: 90_000 });

  const id = (await page.getByTestId("lab-session-id").innerText()).trim();
  expect(id).toMatch(/^[0-9a-f]{16}$/);
  expect(readSessionFile(id)?.label).toEqual(LABEL);
  const text = await page.locator("main").innerText();
  for (const word of FORBIDDEN_WORDS) expect(text, word).not.toContain(word);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);

  // "Record another (same settings)" makes a new session with the same label.
  await page.getByRole("button", { name: "Record another (same settings)" }).click();
  await expect(page.getByRole("heading", { name: "Hand the device to the person" })).toBeVisible();
});
