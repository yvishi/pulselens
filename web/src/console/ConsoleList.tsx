import { useState } from "react";
import { Link } from "react-router-dom";
import { listSessions } from "../api/client";
import type { SessionSummary } from "../contracts";
import "./console.css";
import { OUTCOME_TITLE } from "./OutcomeBanner";
import { NewSession } from "./NewSession";
import { PasscodeGate } from "./PasscodeGate";
import { POLL_ERROR_TEXT, usePoll } from "./usePoll";

const POLL_MS = 2000;
const RESET_KEY = "pulselens.reset_after_ms";

function storedCutoff(): number | null {
  const raw = localStorage.getItem(RESET_KEY);
  const n = raw === null ? NaN : Number(raw);
  return Number.isFinite(n) ? n : null;
}

/** Rows created after `cutoff` (a server created_at_ms value); null shows all. */
export function visibleRows(rows: SessionSummary[], cutoff: number | null): SessionSummary[] {
  return cutoff === null ? rows : rows.filter((r) => r.created_at_ms > cutoff);
}

function SessionTable({ passcode, onUnauthorized }: { passcode: string; onUnauthorized: () => void }) {
  const { value: rows, error: pollError } = usePoll(() => listSessions(passcode), POLL_MS, { onUnauthorized, key: passcode });
  const error = pollError && POLL_ERROR_TEXT[pollError];
  const [cutoff, setCutoff] = useState<number | null>(storedCutoff);
  const shown = rows === null ? null : visibleRows(rows, cutoff);

  const reset = () => {
    if (rows === null || rows.length === 0) return;
    const next = Math.max(...rows.map((r) => r.created_at_ms));
    localStorage.setItem(RESET_KEY, String(next));
    setCutoff(next);
  };
  const showAll = () => {
    localStorage.removeItem(RESET_KEY);
    setCutoff(null);
  };

  return (
    <main className="console">
      <h1>Agent console</h1>
      <NewSession />
      {((rows !== null && rows.length > 0) || cutoff !== null) && (
        <p>
          {rows !== null && rows.length > 0 && (
            <button type="button" onClick={reset}>
              Reset demo
            </button>
          )}{" "}
          {cutoff !== null && (
            <button type="button" onClick={showAll}>
              Show all
            </button>
          )}
        </p>
      )}
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {rows === null && !error && <p>Loading sessions…</p>}
      {shown !== null && shown.length === 0 && <p>No sessions yet.</p>}
      {shown !== null && shown.length > 0 && (
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
            {shown.map((r) => (
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
