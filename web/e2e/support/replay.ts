// Y10 replay e2e helpers: a genuine recorded session turned into a fake-camera .y4m, and a server with REAL analysis.
//
// playwright.config.ts (Keshav's) starts the shared server on :8000 with PULSE_FAKE_ANALYSIS=1, so the replay test
// starts its own server here on REPLAY_API_PORT (default 8001) with PULSE_FAKE_ANALYSIS=0 and PULSE_DATA_DIR=data/e2e,
// and routes the page's /api calls to it. Vite on :5173 still serves the app.
import { spawn, spawnSync, type ChildProcess } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import type { APIRequestContext } from "@playwright/test";
import type { SessionReport } from "../../src/contracts";

const ROOT = path.resolve(import.meta.dirname, "../../..");
const VENV_PY = path.join(ROOT, process.platform === "win32" ? ".venv/Scripts/python.exe" : ".venv/bin/python");
export const REPLAY_PORT = Number(process.env.REPLAY_API_PORT ?? 8001);
export const REPLAY_API = `http://127.0.0.1:${REPLAY_PORT}`;
// data/ is gitignored: the y4m holds a real face and is never committed (AGENTS.md rule 8).
export const REPLAY_Y4M = path.join(ROOT, "data", "e2e-fixtures", "replay.y4m");

/** Converts the session bundle to REPLAY_Y4M with web/e2e/support/bundle_to_y4m.py. */
export function bundleToY4m(sessionDir: string, out = REPLAY_Y4M): string {
  const dir = path.resolve(ROOT, sessionDir);
  if (!existsSync(path.join(dir, "frames.jsonl"))) throw new Error(`${dir} has no frames.jsonl`);
  const script = path.join(import.meta.dirname, "bundle_to_y4m.py");
  const r = spawnSync(VENV_PY, [script, dir, out], { cwd: ROOT, encoding: "utf8" });
  if (r.status !== 0) throw new Error(`bundle_to_y4m failed (${r.status}): ${r.stderr || r.error}`);
  return out;
}

/** Starts uvicorn with real analysis on REPLAY_PORT and waits for /api/health. */
export async function startRealServer(request: APIRequestContext, passcode: string): Promise<ChildProcess> {
  const env = { ...process.env, PULSE_FAKE_ANALYSIS: "0", PULSE_DATA_DIR: "data/e2e", AGENT_PASSCODE: passcode };
  const args = ["-m", "uvicorn", "pulselens.api.main:app", "--app-dir", "server", "--host", "127.0.0.1"];
  const proc = spawn(VENV_PY, [...args, "--port", String(REPLAY_PORT)], { cwd: ROOT, env, stdio: "inherit" });
  const deadline = Date.now() + 60_000;
  while (Date.now() < deadline) {
    if (proc.exitCode !== null) throw new Error(`real-analysis server exited with ${proc.exitCode}`);
    const ok = await request.get(`${REPLAY_API}/api/health`).then((r) => r.ok(), () => false);
    if (ok) return proc;
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  stopServer(proc);
  throw new Error(`real-analysis server did not answer on ${REPLAY_API} within 60 s`);
}

/** Stops the server and its children (on Windows the venv python.exe is a launcher with a child python). */
export function stopServer(proc: ChildProcess): void {
  if (proc.exitCode !== null || proc.pid === undefined) return;
  if (process.platform === "win32") spawnSync("taskkill", ["/pid", String(proc.pid), "/T", "/F"], { stdio: "ignore" });
  else proc.kill();
}

/** Polls the agent API until the session has a decision. */
export async function waitForReport(
  request: APIRequestContext,
  id: string,
  passcode: string,
  timeoutMs = 240_000,
): Promise<SessionReport> {
  const deadline = Date.now() + timeoutMs;
  let last = "";
  while (Date.now() < deadline) {
    const r = await request.get(`${REPLAY_API}/api/sessions/${id}/result`, { headers: { "X-Agent-Passcode": passcode } });
    if (r.ok()) {
      const report = (await r.json()) as SessionReport;
      if (report.decision) return report;
      last = report.state;
    } else {
      last = `${r.status()} ${await r.text()}`;
      if (r.status() >= 500) throw new Error(`agent API GET /result failed for ${id}: ${last}`);
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  throw new Error(`no decision for ${id} within ${timeoutMs} ms (last: ${last})`);
}
