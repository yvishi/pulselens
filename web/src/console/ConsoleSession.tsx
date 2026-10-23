import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError, getResult } from "../api/client";
import type { Family, SessionReport } from "../contracts";
import { HonestyLabel } from "../shared/HonestyLabel";
import { AgentActions } from "./AgentActions";
import "./console.css";
import { EvidenceFrames } from "./EvidenceFrames";
import { FamilyCard } from "./FamilyCard";
import { OutcomeBanner } from "./OutcomeBanner";
import { PasscodeGate } from "./PasscodeGate";
import { modeReason } from "./reasonText";
import { Timeline } from "./Timeline";

const POLL_MS = 1000;
const FAMILIES: Family[] = ["A", "B", "C", "D"];

function Review({ sessionId, passcode, onUnauthorized }: { sessionId: string; passcode: string; onUnauthorized: () => void }) {
  const [report, setReport] = useState<SessionReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  const refresh = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const poll = async () => {
      try {
        const r = await getResult(sessionId, passcode);
        if (!alive) return;
        setReport(r);
        setError(null);
        if (r.decision) return; // decided: stop polling until an action refreshes
      } catch (e) {
        if (!alive) return;
        if (e instanceof ApiError && e.status === 401) return onUnauthorized();
        setError(e instanceof ApiError && e.status === 404 ? "Unknown session." : "The PulseLens server is unreachable. Retrying…");
        if (e instanceof ApiError && e.status === 404) return;
      }
      if (alive) timer = setTimeout(poll, POLL_MS);
    };
    void poll();
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [sessionId, passcode, onUnauthorized, tick]);

  if (!report) {
    return (
      <main className="console">
        <p>
          <Link to="/console">← All sessions</Link>
        </p>
        {error ? <p role="alert" className="error">{error}</p> : <p>Loading session…</p>}
      </main>
    );
  }

  const decision = report.decision;
  const fake = report.results.some((r) => r.check_id.startsWith("fake."));
  const summaries = new Map(decision?.families.map((f) => [f.family, f]));
  return (
    <main className="console">
      <p>
        <Link to="/console">← All sessions</Link>
      </p>
      <header className="session-head">
        <h1>V-CIP session {report.session_id}</h1>
        <p>
          {report.product.replace("_", " ")} · attempt {report.attempt} · {report.state}
          {report.label ? ` · lab recording: ${report.label.kind} (${report.label.person}, ${report.label.device})` : ""}
        </p>
        <div className="labels">
          {decision?.provisional && <HonestyLabel kind="PROVISIONAL THRESHOLDS" />}
          {fake && <HonestyLabel kind="FAKE ANALYSIS" />}
        </div>
        {report.plan && (
          <div className="plan">
            <strong>Plan used: {report.plan.mode}</strong>
            {report.preflight && ` · ${report.preflight.browser}, ${report.preflight.measured_fps.toFixed(1)} fps`}
            <ul>
              {report.plan.reasons.map((code) => (
                <li key={code}>{modeReason(code)}</li>
              ))}
            </ul>
          </div>
        )}
      </header>
      {error && <p role="alert" className="error">{error}</p>}
      <OutcomeBanner decision={decision} />
      <Timeline challenge={report.challenge} events={report.events} />
      <section className="families" aria-label="Evidence by family">
        <h2>Evidence by family</h2>
        <div className="family-grid">
          {FAMILIES.map((f) => {
            const results = report.results.filter((r) => r.family === f);
            const summary = summaries.get(f) ?? {
              family: f, state: results.length ? "abstained" : "not_run", usable_checks: 0, flagged_checks: 0, reasons: [],
            };
            return <FamilyCard key={f} summary={summary} results={results} />;
          })}
        </div>
      </section>
      <EvidenceFrames report={report} passcode={passcode} />
      <AgentActions sessionId={report.session_id} product={report.product} passcode={passcode}
        hasDecision={Boolean(decision)} recorded={report.agent_decision} onRecorded={refresh} />
    </main>
  );
}

export function ConsoleSession() {
  const { sessionId = "" } = useParams();
  return (
    <PasscodeGate>
      {(passcode, onUnauthorized) => <Review sessionId={sessionId} passcode={passcode} onUnauthorized={onUnauthorized} />}
    </PasscodeGate>
  );
}
