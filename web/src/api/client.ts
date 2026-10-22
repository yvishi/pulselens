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

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
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
  if (r.status === 202 || r.status === 204) return undefined as T;
  return (await r.json()) as T;
}

export function createSession(body: SessionCreate): Promise<SessionCreated> {
  return request("/api/sessions", { method: "POST", headers: json, body: JSON.stringify(body) });
}

export function postPreflight(id: string, token: string, body: Preflight): Promise<Plan> {
  return request(`/api/sessions/${id}/preflight`, {
    method: "POST",
    headers: { ...json, ...customer(token) },
    body: JSON.stringify(body),
  });
}

export function getChallenge(id: string, token: string): Promise<Challenge> {
  return request(`/api/sessions/${id}/challenge`, { headers: customer(token) });
}

/** jpegs[i] belongs to meta.frames[i]; each is sent as the multipart part `f{idx}`. */
export function postFrames(id: string, token: string, meta: FrameBatchMeta, jpegs: Blob[]): Promise<void> {
  if (jpegs.length !== meta.frames.length) throw new Error("postFrames: one JPEG per frame in meta.frames");
  const form = new FormData();
  form.append("meta", JSON.stringify(meta));
  meta.frames.forEach((f, i) => form.append(`f${f.idx}`, jpegs[i]!, `${f.idx}.jpg`));
  return request(`/api/sessions/${id}/frames`, { method: "POST", headers: customer(token), body: form });
}

export function postEvents(id: string, token: string, events: ChallengeEvent[]): Promise<void> {
  return request(`/api/sessions/${id}/events`, {
    method: "POST",
    headers: { ...json, ...customer(token) },
    body: JSON.stringify(events),
  });
}

export function completeSession(id: string, token: string): Promise<void> {
  return request(`/api/sessions/${id}/complete`, { method: "POST", headers: customer(token) });
}

export function getStatus(id: string, token: string): Promise<CustomerStatus> {
  return request(`/api/sessions/${id}/status`, { headers: customer(token) });
}

export function listSessions(passcode: string): Promise<SessionSummary[]> {
  return request("/api/sessions", { headers: agent(passcode) });
}

export function getResult(id: string, passcode: string): Promise<SessionReport> {
  return request(`/api/sessions/${id}/result`, { headers: agent(passcode) });
}

export function frameUrl(id: string, idx: number): string {
  return `/api/sessions/${id}/frames/${idx}.jpg`;
}

export function postAgentDecision(id: string, passcode: string, body: AgentDecision): Promise<void> {
  return request(`/api/sessions/${id}/agent`, {
    method: "POST",
    headers: { ...json, ...agent(passcode) },
    body: JSON.stringify(body),
  });
}
