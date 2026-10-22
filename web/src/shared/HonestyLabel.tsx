// Visible label for any number that is not a measured, calibrated result (AGENTS.md rule 6).
export type HonestyKind = "PROVISIONAL THRESHOLDS" | "FAKE ANALYSIS" | "SYNTHETIC" | "ILLUSTRATIVE";

export function HonestyLabel({ kind }: { kind: HonestyKind }) {
  return (
    <span className="honesty" role="note">
      {kind}
    </span>
  );
}
