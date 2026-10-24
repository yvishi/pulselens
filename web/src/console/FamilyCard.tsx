import type { CheckResult, Family, FamilyState, FamilySummary } from "../contracts";
import { CheckPlot } from "./CheckPlot";

export const FAMILY_NAME: Record<Family, string> = {
  A: "Pulse",
  B: "Sensor and stream",
  C: "Light challenge",
  D: "Visual and motion",
};

/** Each family as the question an agent would ask. */
export const FAMILY_QUESTION: Record<Family, string> = {
  A: "Is there a pulse in the skin?",
  B: "Is it a real, live camera?",
  C: "Did the face react to the screen's light?",
  D: "Does the face look and move naturally?",
};

/** The family's answer in plain words, and the tone class for its chip. */
export const FAMILY_ANSWER: Record<FamilyState | "pending", { text: string; tone: string }> = {
  flag: { text: "Problem found", tone: "tone-stop" },
  not_raised: { text: "No problem found", tone: "tone-ok" },
  abstained: { text: "Couldn't tell", tone: "tone-warn" },
  not_run: { text: "Not checked", tone: "" },
  pending: { text: "Analysing…", tone: "" },
};

const EXPERIMENTAL = "Experimental, not used in the decision.";

export function AnswerChip({ state }: { state: FamilyState | "pending" }) {
  const a = FAMILY_ANSWER[state];
  return <span className={`chip state-${state} ${a.tone}`.trim()}>{a.text}</span>;
}

/** The four answers at a glance, as a 2x2 grid of plain questions. */
export function FamilyAnswers({ summaries }: { summaries: Map<Family, FamilySummary> }) {
  return (
    <ul className="answers">
      {(Object.keys(FAMILY_NAME) as Family[]).map((f) => {
        const state = summaries.get(f)?.state ?? "pending";
        return (
          <li key={f} className={`answer answer-${state}${f === "A" ? " answer-experimental" : ""}`}>
            <span className="answer-q">{FAMILY_QUESTION[f]}</span>
            <AnswerChip state={state} />
            {f === "A" && <span className="answer-note muted">{EXPERIMENTAL}</span>}
          </li>
        );
      })}
    </ul>
  );
}

function Check({ r }: { r: CheckResult }) {
  const features = Object.entries(r.features ?? {});
  return (
    <details className={`check check-${r.status}${r.flag ? " check-flag" : ""}`}>
      <summary>
        <code>{r.check_id}</code> <span>{r.explanation}</span>
      </summary>
      <dl className="check-meta">
        <div>
          <dt>Status</dt>
          <dd>
            {r.status}
            {r.status === "usable" ? `, risk ${r.risk?.toFixed(2)}` : ""}
          </dd>
        </div>
        <div>
          <dt>Quality</dt>
          <dd>{r.quality.toFixed(2)}</dd>
        </div>
        <div>
          <dt>Threshold</dt>
          <dd>{r.threshold_source}</dd>
        </div>
        {r.reason_codes && r.reason_codes.length > 0 && (
          <div>
            <dt>Reasons</dt>
            <dd>{r.reason_codes.join(", ")}</dd>
          </div>
        )}
      </dl>
      {features.length > 0 && (
        <div className="features-wrap">
          <table className="features" aria-label={`Features of ${r.check_id}`}>
            <tbody>
              {features.map(([k, v]) => (
                <tr key={k}>
                  <th scope="row">{k}</th>
                  <td>{Number.isInteger(v) ? v : v.toFixed(4)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {r.plot && <CheckPlot plot={r.plot} title={r.check_id} />}
    </details>
  );
}

function Group({ title, results }: { title: string; results: CheckResult[] }) {
  if (!results.length) return null;
  return (
    <div className="check-group">
      <h4>{title}</h4>
      {results.map((r, k) => (
        <Check key={`${r.check_id}-${k}`} r={r} />
      ))}
    </div>
  );
}

/** One evidence family for specialists: its answer, and its checks split into raised risk, could not judge, and checked. */
export function FamilyCard({ family, summary, results }: { family: Family; summary: FamilySummary | null; results: CheckResult[] }) {
  const raised = results.filter((r) => r.status === "protocol_error" || (r.status === "usable" && r.flag));
  const abstained = results.filter((r) => r.status === "abstain");
  const clean = results.filter((r) => r.status === "usable" && !r.flag);
  const state = summary?.state ?? "pending";
  return (
    <section className={`family family-${state}`} aria-label={`Family ${family}: ${FAMILY_NAME[family]}`}>
      <header>
        <div>
          <p className="family-code">
            Family {family} · {FAMILY_NAME[family]}
          </p>
          <h3>{FAMILY_QUESTION[family]}</h3>
        </div>
        <AnswerChip state={state} />
      </header>
      {family === "A" && <p className="note">{EXPERIMENTAL}</p>}
      {summary && !results.length && <p className="muted">No check of this family ran in this session.</p>}
      <Group title="Raised risk" results={raised} />
      <Group title="Could not judge" results={abstained} />
      <Group title="Checked, no risk" results={clean} />
    </section>
  );
}
