import { useEffect, useState, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { getResult, listSessions } from "../api/client";
import type { Family, Platform, SessionReport } from "../contracts";
import { HonestyLabel } from "../shared/HonestyLabel";
import { AgentActions } from "./AgentActions";
import "./console.css";
import { EvidenceFrames } from "./EvidenceFrames";
import { FamilyAnswers, FamilyCard } from "./FamilyCard";
import { OutcomeBanner } from "./OutcomeBanner";
import { PasscodeGate } from "./PasscodeGate";
import { MODE_PLAIN, PRODUCT_PLAIN, STATE_PLAIN, labelKindPlain } from "./plain";
import { modeReason } from "./reasonText";
import { Timeline } from "./Timeline";
import { POLL_ERROR_TEXT, usePoll } from "./usePoll";

const PLATFORM_PLAIN: Record<Platform, string> = { android: "an Android phone", ios: "an iPhone", desktop: "a computer", unknown: "an unknown device" };
const POLL_MS = 1000;
const FAMILIES: Family[] = ["A", "B", "C", "D"];
const ATTEMPT_WORD = ["First", "Second", "Third"];

const attemptText = (n: number) => (ATTEMPT_WORD[n - 1] ? `${ATTEMPT_WORD[n - 1]} attempt` : `Attempt ${n}`);

interface Siblings {
  newer: string | null;
  older: string | null;
}

/** The sessions just newer and just older than this one, from one fetch of the list (no polling). */
function useSiblings(sessionId: string, passcode: string): Siblings | null {
  const [siblings, setSiblings] = useState<Siblings | null>(null);
  useEffect(() => {
    let alive = true;
    Promise.resolve()
      .then(() => listSessions(passcode))
      .then((list) => {
        if (!alive || !Array.isArray(list)) return;
        const sorted = [...list].sort((a, b) => b.created_at_ms - a.created_at_ms);
        const k = sorted.findIndex((s) => s.session_id === sessionId);
        if (k < 0) return;
        setSiblings({ newer: sorted[k - 1]?.session_id ?? null, older: sorted[k + 1]?.session_id ?? null });
      })
      .catch(() => undefined); // navigation is a convenience: the page works without it
    return () => {
      alive = false;
    };
  }, [sessionId, passcode]);
  return siblings;
}

function TopNav({ sessionId, siblings }: { sessionId: string; siblings: Siblings | null }) {
  const step = (id: string | null | undefined, label: string, rel: string) =>
    id ? (
      <Link to={`/console/${id}`} className="btn btn-quiet" rel={rel}>
        {label}
      </Link>
    ) : (
      <span className="btn btn-quiet is-disabled" aria-disabled="true">
        {label}
      </span>
    );
  return (
    <div className="review-nav">
      <nav aria-label="Breadcrumb" className="crumbs">
        <ol>
          <li>
            <Link to="/console">Verifications</Link>
          </li>
          <li aria-current="page">
            Session <span className="mono">{sessionId}</span>
          </li>
        </ol>
      </nav>
      <nav aria-label="Other sessions" className="siblings">
        {step(siblings?.newer, "← Newer session", "prev")}
        {step(siblings?.older, "Older session →", "next")}
      </nav>
    </div>
  );
}

/** How the customer's check ran: the plan in plain words, the device, and what the screen showed. */
function Journey({ report }: { report: SessionReport }) {
  const { plan, preflight } = report;
  return (
    <section className="journey card" aria-labelledby="journey-title">
      <h2 id="journey-title">How the check went</h2>
      {plan ? (
        <>
          <p className="journey-plan">
            <span className="chip tone-stamp">{MODE_PLAIN[plan.mode]}</span>
          </p>
          <ul className="journey-reasons">
            {plan.reasons.map((code) => (
              <li key={code}>{modeReason(code)}</li>
            ))}
            {plan.agent_questions && <li>The agent should ask the customer a few questions on the call.</li>}
          </ul>
        </>
      ) : (
        <p className="muted">The customer has not started the check yet.</p>
      )}
      {preflight && (
        <p className="muted journey-device">
          {preflight.browser} on {PLATFORM_PLAIN[preflight.platform]} ·{" "}
          {preflight.measured_fps.toFixed(1)} frames per second · {preflight.width}×{preflight.height}
        </p>
      )}
      <Timeline challenge={report.challenge} events={report.events} />
    </section>
  );
}

function Notes({ provisional, fake }: { provisional: boolean; fake: boolean }) {
  if (!provisional && !fake) return null;
  return (
    <div className="honesty-notes">
      {provisional && (
        <p>
          <HonestyLabel kind="PROVISIONAL THRESHOLDS" />{" "}
          <span className="muted">Thresholds are not yet calibrated: treat the recommendation as a guide.</span>
        </p>
      )}
      {fake && (
        <p>
          <HonestyLabel kind="FAKE ANALYSIS" />{" "}
          <span className="muted">These results come from a stand-in used for testing, not from real measurements.</span>
        </p>
      )}
    </div>
  );
}

function Shell({ sessionId, siblings, children }: { sessionId: string; siblings: Siblings | null; children: ReactNode }) {
  return (
    <main className="console review-page shell-page">
      <TopNav sessionId={sessionId} siblings={siblings} />
      {children}
    </main>
  );
}

function Review({ sessionId, passcode, onUnauthorized }: { sessionId: string; passcode: string; onUnauthorized: () => void }) {
  const [actions, setActions] = useState(0); // bumped after an agent action, to fetch the report again
  const siblings = useSiblings(sessionId, passcode);
  const { value: report, error: pollError } = usePoll(() => getResult(sessionId, passcode), POLL_MS, {
    done: (r) => r.decision !== null, // decided: nothing changes until the agent acts
    onUnauthorized,
    key: `${sessionId}|${passcode}|${actions}`,
  });
  const error = pollError && POLL_ERROR_TEXT[pollError];

  if (!report) {
    return (
      <Shell sessionId={sessionId} siblings={siblings}>
        {error ? (
          <div className="card review-empty">
            <p role="alert" className="error">
              {pollError === "not_found" ? "We could not find this verification." : error}
            </p>
            <p className="muted">
              {pollError === "not_found" ? "The link may be mistyped, or the session was removed. " : ""}
              <Link to="/console">Back to all verifications</Link>
            </p>
          </div>
        ) : (
          <p className="loading">Loading this verification…</p>
        )}
      </Shell>
    );
  }

  const decision = report.decision;
  const fake = report.results.some((r) => r.check_id.startsWith("fake."));
  const summaries = new Map(decision?.families.map((f) => [f.family, f]));
  return (
    <Shell sessionId={sessionId} siblings={siblings}>
      <div className="review">
        <header className="review-head">
          <p className="eyebrow">Video KYC liveness check</p>
          <h1>{PRODUCT_PLAIN[report.product]} verification</h1>
          <p className="review-meta">
            <span className="chip">{STATE_PLAIN[report.state]}</span>
            <span>{attemptText(report.attempt)}</span>
            <span className="mono muted">{report.session_id}</span>
          </p>
          {report.label && (
            <p className="lab-label muted">
              Lab recording: {labelKindPlain(report.label.kind)} ({report.label.person}, {report.label.device})
            </p>
          )}
          {error && (
            <p role="alert" className="error">
              {error}
            </p>
          )}
        </header>

        <div className="review-verdict">
          <OutcomeBanner decision={decision} state={report.state} notes={<Notes provisional={Boolean(decision?.provisional)} fake={fake} />} />
        </div>

        <aside className="review-decide" aria-label="Decision panel">
          <div className="decide-sticky">
            <AgentActions sessionId={report.session_id} product={report.product} passcode={passcode}
              hasDecision={Boolean(decision)} recorded={report.agent_decision} outcome={decision?.outcome ?? null}
              onRecorded={() => setActions((n) => n + 1)} />
          </div>
        </aside>

        <section className="review-checked card" aria-labelledby="checked-title">
          <h2 id="checked-title">What PulseLens checked</h2>
          <FamilyAnswers summaries={summaries} />
        </section>

        <div className="review-journey">
          <Journey report={report} />
        </div>

        <details className="tech card">
          <summary>
            <span className="tech-title">Technical details (for specialists)</span>
            <span className="muted tech-hint">Every check with its numbers and plots, and camera frames.</span>
          </summary>
          <div className="tech-body">
            <dl className="tech-facts">
              <div>
                <dt>Session state</dt>
                <dd className="mono">{report.state}</dd>
              </div>
              {report.plan && (
                <div>
                  <dt>Plan</dt>
                  <dd className="mono">
                    {report.plan.mode} ({report.plan.reasons.join(", ")})
                  </dd>
                </div>
              )}
              {report.preflight && (
                <div>
                  <dt>Camera</dt>
                  <dd>
                    {report.preflight.camera_label}, dropped frames {(report.preflight.dropped_frame_ratio * 100).toFixed(1)}%, clock{" "}
                    {report.preflight.clock}
                  </dd>
                </div>
              )}
              <div>
                <dt>Frames received</dt>
                <dd>{report.frame_count}</dd>
              </div>
            </dl>
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
          </div>
        </details>
      </div>
    </Shell>
  );
}

export function ConsoleSession() {
  const { sessionId = "" } = useParams();
  return (
    <PasscodeGate>
      {(passcode, onUnauthorized) => <Review key={sessionId} sessionId={sessionId} passcode={passcode} onUnauthorized={onUnauthorized} />}
    </PasscodeGate>
  );
}
