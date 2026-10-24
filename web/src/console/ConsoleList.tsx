import { Link } from "react-router-dom";
import { listSessions } from "../api/client";
import "./console.css";
import { OUTCOME_TITLE } from "./OutcomeBanner";
import { NewSession } from "./NewSession";
import { PasscodeGate } from "./PasscodeGate";
import { POLL_ERROR_TEXT, usePoll } from "./usePoll";

const POLL_MS = 2000;

function SessionTable({ passcode, onUnauthorized }: { passcode: string; onUnauthorized: () => void }) {
  const { value: rows, error: pollError } = usePoll(() => listSessions(passcode), POLL_MS, { onUnauthorized, key: passcode });
  const error = pollError && POLL_ERROR_TEXT[pollError];

  return (
    <main className="console">
      <h1>Agent console</h1>
      <NewSession />
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
