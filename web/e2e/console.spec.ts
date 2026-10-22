import { expect, test } from "@playwright/test";

// K1 smoke: the web app loads, and /api reaches the server through the Vite proxy. K7 adds the console tests.
test("home loads and the server is reachable through the proxy", async ({ page, request }) => {
  await page.goto("http://localhost:5173/");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("PulseLens");
  const health = await request.get("http://localhost:5173/api/health");
  expect(await health.json()).toEqual({ ok: true });
});
