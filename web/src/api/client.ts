// Typed client for every row of the API table (docs/CONTRACT.md section 2). Owned by Keshav.
import type {
  AgentDecision,
  Challenge,
  ChallengeEvent,
  CustomerStatus,
  FrameBatchMeta,
  Plan,
  Preflight,
  SessionCreate,
  SessionCreated,
  SessionReport,
  SessionSummary,
} from "../contracts";

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(`${status}: ${detail}`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

const customer = (token: string) => ({ Authorization: `Bearer ${token}` });
const agent = (passcode: string) => ({ "X-Agent-Passcode": passcode });
const json = { "Content-Type": "application/json" };

/** The response, or ApiError with the server's detail on a non-2xx status. */
async function send(path: string, init: RequestInit = {}): Promise<Response> {
  const r = await fetch(path, init);
  if (!r.ok) {
    let detail = r.statusText;
    try {
      const body = await r.json();
      detail = typeof body?.detail === "string" ? body.detail : JSON.stringify(body?.detail ?? body);
    } catch {
      // not JSON: keep the status text
    }
    throw new ApiError(r.status, detail);
  }
  return r;
}

/** A JSON body typed by the contract; the server's pydantic models guarantee the shape. */
async function requestJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  return (await (await send(path, init)).json()) as T;
}

/** 202 and 204 responses: no body. */
async function requestVoid(path: string, init: RequestInit = {}): Promise<void> {
  await send(path, init);
}

export function createSession(body: SessionCreate): Promise<SessionCreated> {
  return requestJson("/api/sessions", { method: "POST", headers: json, body: JSON.stringify(body) });
}

export function postPreflight(id: string, token: string, body: Preflight): Promise<Plan> {
  return requestJson(`/api/sessions/${id}/preflight`, {
    method: "POST",
    headers: { ...json, ...customer(token) },
    body: JSON.stringify(body),
  });
}

export function getChallenge(id: string, token: string): Promise<Challenge> {
  return requestJson(`/api/sessions/${id}/challenge`, { headers: customer(token) });
}

/** jpegs[i] belongs to meta.frames[i]; each is sent as the multipart part `f{idx}`. */
export function postFrames(id: string, token: string, meta: FrameBatchMeta, jpegs: Blob[]): Promise<void> {
  if (jpegs.length !== meta.frames.length) throw new Error("postFrames: one JPEG per frame in meta.frames");
  const form = new FormData();
  form.append("meta", JSON.stringify(meta));
  meta.frames.forEach((f, i) => form.append(`f${f.idx}`, jpegs[i]!, `${f.idx}.jpg`));
  return requestVoid(`/api/sessions/${id}/frames`, { method: "POST", headers: customer(token), body: form });
}

export function postEvents(id: string, token: string, events: ChallengeEvent[]): Promise<void> {
  return requestVoid(`/api/sessions/${id}/events`, {
    method: "POST",
    headers: { ...json, ...customer(token) },
    body: JSON.stringify(events),
  });
}

export function completeSession(id: string, token: string): Promise<void> {
  return requestVoid(`/api/sessions/${id}/complete`, { method: "POST", headers: customer(token) });
}

export function getStatus(id: string, token: string): Promise<CustomerStatus> {
  return requestJson(`/api/sessions/${id}/status`, { headers: customer(token) });
}

export function listSessions(passcode: string): Promise<SessionSummary[]> {
  return requestJson("/api/sessions", { headers: agent(passcode) });
}

export function getResult(id: string, passcode: string): Promise<SessionReport> {
  return requestJson(`/api/sessions/${id}/result`, { headers: agent(passcode) });
}

export function frameUrl(id: string, idx: number): string {
  return `/api/sessions/${id}/frames/${idx}.jpg`;
}

export function postAgentDecision(id: string, passcode: string, body: AgentDecision): Promise<void> {
  return requestVoid(`/api/sessions/${id}/agent`, {
    method: "POST",
    headers: { ...json, ...agent(passcode) },
    body: JSON.stringify(body),
  });
}
