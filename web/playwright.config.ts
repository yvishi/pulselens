import { defineConfig } from "@playwright/test";
import path from "node:path";

// e2e drives the installed Brave, headed, with Chromium's fake camera flags: no browser download.
// BRAVE_PATH overrides the install location. It starts its own server and Vite and never reuses running ones,
// which write to data/sessions (volunteer data): stop dev servers before `python scripts/dev.py e2e`.
const root = path.resolve(import.meta.dirname, "..");
const venvPython = path.join(root, process.platform === "win32" ? ".venv/Scripts/python.exe" : ".venv/bin/python");
const bravePath =
  process.env.BRAVE_PATH ??
  (process.platform === "win32"
    ? "C:/Program Files/BraveSoftware/Brave-Browser/Application/brave.exe"
    : process.platform === "darwin"
      ? "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"
      : "/usr/bin/brave-browser");
const fakeCamera = ["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream"];

export default defineConfig({
  testDir: "e2e",
  reporter: [["list"]],
  use: { trace: "retain-on-failure", viewport: { width: 1280, height: 720 }, permissions: ["camera"] },
  projects: [
    { name: "brave", use: { headless: false, launchOptions: { executablePath: bravePath, args: fakeCamera } } },
    // Opt-in only: `npx playwright install chromium` in web/, then `--project=chromium`.
    { name: "chromium", use: { browserName: "chromium", launchOptions: { args: fakeCamera } } },
  ],
  webServer: [
    {
      command: `"${venvPython}" -m uvicorn pulselens.api.main:app --app-dir server --host 127.0.0.1 --port 8000`,
      cwd: root,
      url: "http://127.0.0.1:8000/api/health",
      reuseExistingServer: false,
      env: { PULSE_FAKE_ANALYSIS: "1", PULSE_DATA_DIR: "data/e2e", AGENT_PASSCODE: "e2e-passcode" },
    },
    { command: "npm run dev", url: "http://localhost:5173", reuseExistingServer: false },
  ],
});
