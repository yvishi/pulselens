// e2e helper: the session.json the server wrote to data/e2e (PULSE_DATA_DIR, set by playwright.config.ts).
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import type { Label } from "../../src/contracts";
import { DATA } from "./bundle";

export interface SessionFile {
  session_id: string;
  state: string;
  label: Label | null;
}

export function readSessionFile(id: string): SessionFile | null {
  const file = path.join(DATA, id, "session.json");
  return existsSync(file) ? (JSON.parse(readFileSync(file, "utf8")) as SessionFile) : null;
}
