import { useEffect, useId, useState, type MouseEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { listSessions } from "../api/client";
import type { SessionSummary } from "../contracts";
import "./console.css";
import "./list.css";
import { NewSession } from "./NewSession";
import { PasscodeGate } from "./PasscodeGate";
import { labelKindPlain, MODE_PLAIN, OUTCOME_PLAIN, PRODUCT_PLAIN, STATE_PLAIN, timeAgo, wallNow } from "./plain";
import { POLL_ERROR_TEXT, usePoll } from "./usePoll";

const POLL_MS = 2000;
const RESET_KEY = "pulselens.reset_after_ms";

function storedCutoff(): number | null {
  try {
    const raw = localStorage.getItem(RESET_KEY);
    const n = raw === null ? NaN : Number(raw);
    return Number.isFinite(n) ? n : null;
  } catch {
    return null;
  }
}

/** Rows created after `cutoff` (a server created_at_ms value); null shows all. */
export function visibleRows(rows: SessionSummary[], cutoff: number | null): SessionSummary[] {
  return cutoff === null ? rows : rows.filter((r) => r.created_at_ms > cutoff);
}

export type ListFilter = "attention" | "progress" | "all";

const FILTERS: { id: ListFilter; label: string }[] = [
  { id: "attention", label: "Needs attention" },
  { id: "progress", label: "In progress" },
  { id: "all", label: "All" },
];

/** Does this row belong under the filter? Attention: the agent must act; in progress: still running. */
export function matchesFilter(r: SessionSummary, f: ListFilter): boolean {
  if (f === "attention") return r.outcome === "HUMAN_REVIEW" || r.outcome === "RETRY_STEP_UP" || (r.state === "done" && r.outcome === null);
  if (f === "progress") return r.state !== "done" && r.state !== "expired";
  return true;
}

/** The current wall time, refreshed every 30 s so "3 min ago" stays true. */
function useWallClock(): number {
  const [now, setNow] = useState(wallNow);
  useEffect(() => {
    const t = setInterval(() => setNow(wallNow()), 30_000);
    return () => clearInterval(t);
  }, []);
  return now;
}

function ResultCell({ r }: { r: SessionSummary }) {
  if (r.outcome) {
    const o = OUTCOME_PLAIN[r.outcome];
    return (
      <span className="cell-stack">
        <span className={`chip tone-${o.tone}`}>{o.title}</span>
        <span className="code mono">{r.outcome}</span>
      </span>
    );
  }
  if (r.state === "done") return <span className="chip tone-warn">No result</span>;
  if (r.state === "expired") return <span className="muted">None</span>;
  return <span className="muted">Not ready yet</span>;
}

function SessionRow({ r, now }: { r: SessionSummary; now: number }) {
  const navigate = useNavigate();
  const to = `/console/${r.session_id}`;
  const created = new Date(r.created_at_ms);
  const open = (e: MouseEvent<HTMLTableRowElement>) => {
    // The real link in the first cell handles its own clicks; elsewhere the whole row opens the session.
    if ((e.target as HTMLElement).closest("a, button")) return;
    if (window.getSelection()?.toString()) return; // the agent is selecting text, not opening
    navigate(to);
  };

  return (
    <tr className={`row${r.outcome ? ` row-${OUTCOME_PLAIN[r.outcome].tone}` : ""}`} onClick={open}>
      <td data-label="Session" className="cell-session">
        <Link to={to} className="mono session-link">
          {r.session_id}
        </Link>
        {r.attempt > 1 && <span className="sub">Attempt {r.attempt}</span>}
        {r.label_kind && <span className="sub lab">Lab: {labelKindPlain(r.label_kind)}</span>}
      </td>
      <td data-label="Started">
        <span className="cell-stack">
          <span>{timeAgo(r.created_at_ms, now)}</span>
          <time className="sub" dateTime={created.toISOString()}>
            {created.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
            {created.toDateString() !== new Date(now).toDateString() && `, ${created.toLocaleDateString()}`}
          </time>
        </span>
      </td>
      <td data-label="Applying for">{PRODUCT_PLAIN[r.product] ?? r.product}</td>
      <td data-label="Progress">
        <span className={`run-state run-state-${r.state}`}>{STATE_PLAIN[r.state] ?? r.state}</span>
      </td>
      <td data-label="Check type">{r.mode ? MODE_PLAIN[r.mode] : <span className="muted">Not chosen yet</span>}</td>
      <td data-label="Result" className="cell-result">
        <ResultCell r={r} />
      </td>
    </tr>
  );
}

function SessionTable({ passcode, onUnauthorized }: { passcode: string; onUnauthorized: () => void }) {
  const { value: rows, error: pollError } = usePoll(() => listSessions(passcode), POLL_MS, { onUnauthorized, key: passcode });
  const error = pollError && POLL_ERROR_TEXT[pollError];
  const [cutoff, setCutoff] = useState<number | null>(storedCutoff);
  const [filter, setFilter] = useState<ListFilter>("all");
  const [query, setQuery] = useState("");
  const now = useWallClock();
  const searchId = useId();

  const shown = rows === null ? null : [...visibleRows(rows, cutoff)].sort((a, b) => b.created_at_ms - a.created_at_ms);
  const q = query.trim().toLowerCase();
  const filtered = shown?.filter((r) => matchesFilter(r, filter) && (!q || r.session_id.toLowerCase().includes(q))) ?? null;
  const count = (f: ListFilter) => shown?.filter((r) => matchesFilter(r, f)).length ?? 0;

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
  const hasDemoTools = (rows !== null && rows.length > 0) || cutoff !== null;

  return (
    <main className="console shell-page list-page">
      <header className="list-head">
        <h1>Verifications</h1>
        <p className="muted">
          Start a check for the customer on your call, then follow it here. Open a verification to see what PulseLens
          recommends and record your decision.
        </p>
      </header>

      <NewSession />

      <section className="list-section" aria-labelledby={`${searchId}-title`}>
        <div className="list-bar">
          <h2 id={`${searchId}-title`} className="list-title">
            Recent verifications
          </h2>
          {hasDemoTools && (
            <div className="demo-tools" role="group" aria-label="Demo tools">
              <span className="demo-label">Demo tools</span>
              {rows !== null && rows.length > 0 && (
                <button type="button" className="btn btn-quiet" onClick={reset}>
                  Reset demo
                </button>
              )}
              {cutoff !== null && (
                <button type="button" className="btn btn-quiet" onClick={showAll}>
                  Show all
                </button>
              )}
            </div>
          )}
        </div>

        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        {rows === null && !error && <p className="loading">Loading sessions…</p>}

        {shown !== null && shown.length === 0 && (
          <div className="empty">
            <p className="empty-title">No sessions yet.</p>
            <p className="muted">Use “Start a verification” above. Each new check will appear here.</p>
          </div>
        )}

        {shown !== null && shown.length > 0 && filtered !== null && (
          <>
            <div className="list-tools">
              <div className="segmented" role="group" aria-label="Show">
                {FILTERS.map((f) => (
                  <button
                    key={f.id}
                    type="button"
                    className="seg"
                    aria-pressed={filter === f.id}
                    onClick={() => setFilter(f.id)}
                  >
                    {f.label}
                    <span className="seg-count">{count(f.id)}</span>
                  </button>
                ))}
              </div>
              <div className="search">
                <label htmlFor={searchId} className="search-label">
                  Find a session
                </label>
                <input
                  id={searchId}
                  type="search"
                  className="search-input mono"
                  placeholder="Session number"
                  autoComplete="off"
                  spellCheck={false}
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
              </div>
            </div>

            {filtered.length === 0 ? (
              <div className="empty">
                <p className="empty-title">Nothing to show here.</p>
                <p className="muted">
                  {q ? "No session number matches your search." : "No verifications fit this view right now."}{" "}
                  <button
                    type="button"
                    className="btn btn-quiet inline"
                    onClick={() => {
                      setQuery("");
                      setFilter("all");
                    }}
                  >
                    Clear search and filters
                  </button>
                </p>
              </div>
            ) : (
              <table className="sessions list-table" aria-label="Sessions">
                <thead>
                  <tr>
                    <th scope="col">Session</th>
                    <th scope="col">Started</th>
                    <th scope="col">Applying for</th>
                    <th scope="col">Progress</th>
                    <th scope="col">Check type</th>
                    <th scope="col">Result</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((r) => (
                    <SessionRow key={r.session_id} r={r} now={now} />
                  ))}
                </tbody>
              </table>
            )}
          </>
        )}
      </section>
    </main>
  );
}

export function ConsoleList() {
  return <PasscodeGate>{(passcode, onUnauthorized) => <SessionTable passcode={passcode} onUnauthorized={onUnauthorized} />}</PasscodeGate>;
}
