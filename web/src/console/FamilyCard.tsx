import type { CheckResult, Family, FamilyState, FamilySummary } from "../contracts";
import { CheckPlot } from "./CheckPlot";

export const FAMILY_NAME: Record<Family, string> = {
  A: "Pulse",
  B: "Sensor and stream",
  C: "Light challenge",
  D: "Visual and motion",
};

const STATE_CHIP: Record<FamilyState, string> = {
  flag: "FLAG",
  not_raised: "NOT RAISED",
  abstained: "ABSTAINED",
  not_run: "NOT RUN",
};

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

/** One evidence family: its state, and its checks split into raised risk, could not judge, and checked. */
export function FamilyCard({ family, summary, results }: { family: Family; summary: FamilySummary | null; results: CheckResult[] }) {
  const raised = results.filter((r) => r.status === "protocol_error" || (r.status === "usable" && r.flag));
  const abstained = results.filter((r) => r.status === "abstain");
  const clean = results.filter((r) => r.status === "usable" && !r.flag);
  return (
    <section className={`family family-${summary?.state ?? "pending"}`} aria-label={`Family ${family}: ${FAMILY_NAME[family]}`}>
      <header>
        <h3>
          {family} · {FAMILY_NAME[family]}
        </h3>
        <span className={`chip state-${summary?.state ?? "pending"}`}>{summary ? STATE_CHIP[summary.state] : "Analysing…"}</span>
      </header>
      {family === "A" && <p className="note">Experimental, not used in the decision.</p>}
      {summary && !results.length && <p className="muted">No check of this family ran in this session.</p>}
      <Group title="Raised risk" results={raised} />
      <Group title="Could not judge" results={abstained} />
      <Group title="Checked, no risk" results={clean} />
    </section>
  );
}
