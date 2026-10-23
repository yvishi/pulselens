import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, listSessions } from "../api/client";
import type { SessionSummary } from "../contracts";
import "./console.css";
import { OUTCOME_TITLE } from "./OutcomeBanner";
import { PasscodeGate } from "./PasscodeGate";

const POLL_MS = 2000;

function SessionTable({ passcode, onUnauthorized }: { passcode: string; onUnauthorized: () => void }) {
  const [rows, setRows] = useState<SessionSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const poll = async () => {
      try {
        const list = await listSessions(passcode);
        if (!alive) return;
        setRows(list);
        setError(null);
      } catch (e) {
        if (!alive) return;
        if (e instanceof ApiError && e.status === 401) return onUnauthorized();
        setError("The PulseLens server is unreachable. Retrying…");
      }
      if (alive) timer = setTimeout(poll, POLL_MS);
    };
    void poll();
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [passcode, onUnauthorized]);

  return (
    <main className="console">
      <h1>Agent console</h1>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {rows === null && !error && <p>Loading sessions…</p>}
      {rows !== null && rows.length === 0 && <p>No sessions yet.</p>}
      {rows !== null && rows.length > 0 && (
        <table className="sessions" aria-label="Sessions">
          <thead>
            <tr>
              <th>Session</th>
              <th>Created</th>
              <th>Product</th>
              <th>Attempt</th>
              <th>State</th>
              <th>Mode</th>
              <th>Outcome</th>
              <th>Label</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.session_id}>
                <td>
                  <Link to={`/console/${r.session_id}`}>{r.session_id}</Link>
                </td>
                <td>{new Date(r.created_at_ms).toLocaleTimeString()}</td>
                <td>{r.product.replace("_", " ")}</td>
                <td>{r.attempt}</td>
                <td>{r.state}</td>
                <td>{r.mode ?? "–"}</td>
                <td>{r.outcome ? <span className={`chip outcome-${r.outcome}`}>{OUTCOME_TITLE[r.outcome]}</span> : "–"}</td>
                <td>{r.label_kind ?? "–"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </main>
  );
}

export function ConsoleList() {
  return <PasscodeGate>{(passcode, onUnauthorized) => <SessionTable passcode={passcode} onUnauthorized={onUnauthorized} />}</PasscodeGate>;
}
