// e2e helpers for the customer flow: sessions through the real API, and the bundle the server wrote to data/e2e.
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import type { APIRequestContext } from "@playwright/test";
import type { Challenge, ChallengeEvent, FrameMeta, Plan, SessionCreate, SessionCreated } from "../../src/contracts";

export const API = "http://127.0.0.1:8000";
export const WEB = "http://localhost:5173";
export const DATA = path.resolve(import.meta.dirname, "../../../data/e2e");

export async function createSession(
  request: APIRequestContext,
  body: SessionCreate = {},
  api = API,
): Promise<SessionCreated> {
  const r = await request.post(`${api}/api/sessions`, { data: body });
  if (r.status() !== 201) throw new Error(`createSession: ${r.status()} ${await r.text()}`);
  return (await r.json()) as SessionCreated;
}

function json<T>(id: string, name: string): T | null {
  const file = path.join(DATA, id, name);
  return existsSync(file) ? (JSON.parse(readFileSync(file, "utf8")) as T) : null;
}

function jsonl<T>(id: string, name: string): T[] {
  const file = path.join(DATA, id, name);
  if (!existsSync(file)) return [];
  return readFileSync(file, "utf8").split("\n").filter(Boolean).map((l) => JSON.parse(l) as T);
}

export interface BundleOnDisk {
  plan: Plan | null;
  challenge: Challenge | null;
  frames: (FrameMeta & { batch_seq: number })[];
  events: ChallengeEvent[];
}

export function readBundle(id: string): BundleOnDisk {
  return {
    plan: json<Plan>(id, "plan.json"),
    challenge: json<Challenge>(id, "challenge.json"),
    frames: jsonl<FrameMeta & { batch_seq: number }>(id, "frames.jsonl"),
    events: jsonl<ChallengeEvent>(id, "events.jsonl"),
  };
}
