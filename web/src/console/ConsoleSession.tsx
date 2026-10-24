import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getResult } from "../api/client";
import type { Family } from "../contracts";
import { HonestyLabel } from "../shared/HonestyLabel";
import { AgentActions } from "./AgentActions";
import "./console.css";
import { EvidenceFrames } from "./EvidenceFrames";
import { FamilyCard } from "./FamilyCard";
import { OutcomeBanner } from "./OutcomeBanner";
import { PasscodeGate } from "./PasscodeGate";
import { modeReason } from "./reasonText";
import { Timeline } from "./Timeline";
import { POLL_ERROR_TEXT, usePoll } from "./usePoll";

const POLL_MS = 1000;
const FAMILIES: Family[] = ["A", "B", "C", "D"];

function Review({ sessionId, passcode, onUnauthorized }: { sessionId: string; passcode: string; onUnauthorized: () => void }) {
  const [actions, setActions] = useState(0); // bumped after an agent action, to fetch the report again
  const { value: report, error: pollError } = usePoll(() => getResult(sessionId, passcode), POLL_MS, {
    done: (r) => r.decision !== null, // decided: nothing changes until the agent acts
    onUnauthorized,
    key: `${sessionId}|${passcode}|${actions}`,
  });
  const error = pollError && POLL_ERROR_TEXT[pollError];

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
            return <FamilyCard key={f} family={f} summary={summaries.get(f) ?? null} results={results} />;
          })}
        </div>
      </section>
      <EvidenceFrames report={report} passcode={passcode} />
      <AgentActions sessionId={report.session_id} product={report.product} passcode={passcode}
        hasDecision={Boolean(decision)} recorded={report.agent_decision} onRecorded={() => setActions((n) => n + 1)} />
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
