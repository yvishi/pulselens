import { useEffect, useState } from "react";
import { frameUrl } from "../api/client";
import type { SessionReport } from "../contracts";

export interface EvidenceFrame {
  label: string;
  idx: number;
}

/**
 * One frame per shown colour step (at its painted time) and one at the middle of the turn. The report has no
 * per-frame times, so the frame number comes from the measured frame rate: close enough for a thumbnail.
 */
export function pickEvidenceFrames(report: SessionReport, max = 6): EvidenceFrame[] {
  const { challenge, preflight, frame_count } = report;
  if (!challenge || !preflight || frame_count === 0) return [];
  const fps = preflight.measured_fps > 0 ? preflight.measured_fps : 15;
  const at = (ms: number) => Math.max(0, Math.min(frame_count - 1, Math.round((ms * fps) / 1000)));
  const shown = new Map(report.events.filter((e) => e.status === "shown" && e.painted_t_ms !== null).map((e) => [e.step_id, e]));
  const out: EvidenceFrame[] = [];
  for (const s of challenge.steps) {
    const e = shown.get(s.step_id);
    if (s.kind === "colour" && e?.painted_t_ms != null) out.push({ label: `${s.step_id} (hue ${s.hue_deg}°)`, idx: at(e.painted_t_ms) });
    if (s.kind === "turn") {
      const start = e?.painted_t_ms ?? challenge.baseline_ms + s.start_offset_ms;
      out.push({ label: `${s.step_id} turn ${s.direction}`, idx: at(start + s.duration_ms / 2) });
    }
  }
  const colours = out.filter((f) => !f.label.includes("turn")).slice(0, max - 1);
  return [...colours, ...out.filter((f) => f.label.includes("turn"))].slice(0, max);
}

function Thumb({ sessionId, frame, passcode }: { sessionId: string; frame: EvidenceFrame; passcode: string }) {
  const [src, setSrc] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let url: string | null = null;
    let alive = true;
    fetch(frameUrl(sessionId, frame.idx), { headers: { "X-Agent-Passcode": passcode } })
      .then((r) => (r.ok ? r.blob() : Promise.reject(new Error(String(r.status)))))
      .then((blob) => {
        if (!alive) return;
        url = URL.createObjectURL(blob);
        setSrc(url);
      })
      .catch(() => alive && setFailed(true));
    return () => {
      alive = false;
      if (url) URL.revokeObjectURL(url);
    };
  }, [sessionId, frame.idx, passcode]);
  return (
    <figure className="thumb">
      {src ? <img src={src} alt={`Frame ${frame.idx}, ${frame.label}`} /> : <div className="thumb-empty">{failed ? "not available" : "…"}</div>}
      <figcaption>
        {frame.label} · frame {frame.idx}
      </figcaption>
    </figure>
  );
}

export function EvidenceFrames({ report, passcode }: { report: SessionReport; passcode: string }) {
  const frames = pickEvidenceFrames(report);
  if (!frames.length) return null;
  return (
    <section className="evidence" aria-label="Evidence frames">
      <h3>Evidence frames</h3>
      <div className="thumbs">
        {frames.map((f) => (
          <Thumb key={`${f.label}-${f.idx}`} sessionId={report.session_id} frame={f} passcode={passcode} />
        ))}
      </div>
    </section>
  );
}
