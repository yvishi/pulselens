// Small inline drawings for the customer screens. All decorative (aria-hidden): the text beside them says everything.
// Strokes use currentColor, so each one takes its colour from the CSS tokens and works in dark mode.
import type { ReactNode } from "react";
import type { CoachTip } from "../../capture/coaching";

function Svg({ size = 24, className, children }: { size?: number; className?: string; children: ReactNode }) {
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {children}
    </svg>
  );
}

export const LockIcon = () => (
  <Svg size={18}>
    <rect x="5" y="10.5" width="14" height="10" rx="2.5" />
    <path d="M8 10.5V8a4 4 0 0 1 8 0v2.5" />
    <path d="M12 14.5v2.5" />
  </Svg>
);

/** Soft colours on a screen. */
export const ColoursIcon = () => (
  <Svg>
    <rect x="3.5" y="3.5" width="17" height="17" rx="4" />
    <circle cx="9.5" cy="9.5" r="2.3" fill="currentColor" fillOpacity="0.25" />
    <circle cx="14.5" cy="9.5" r="2.3" fill="currentColor" fillOpacity="0.5" />
    <circle cx="12" cy="14.3" r="2.3" fill="currentColor" fillOpacity="0.8" />
  </Svg>
);

/** A head with arrows either side. */
export const TurnIcon = () => (
  <Svg>
    <ellipse cx="12" cy="11" rx="4.2" ry="5.2" />
    <path d="M9.5 19.5c.8.4 1.6.5 2.5.5s1.7-.1 2.5-.5" />
    <path d="M4.5 9 2.5 11l2 2M19.5 9l2 2-2 2" />
  </Svg>
);

export const ClockIcon = () => (
  <Svg>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M12 7.5V12l3 2" />
  </Svg>
);

export const ShieldIcon = () => (
  <Svg size={20}>
    <path d="M12 3.5 5 6v5.5c0 4.2 3 7.6 7 9 4-1.4 7-4.8 7-9V6l-7-2.5Z" />
    <path d="m9 12 2.2 2.2L15.5 10" />
  </Svg>
);

export const CameraIcon = () => (
  <Svg size={56} className="art-icon">
    <path d="M4 8.5A2.5 2.5 0 0 1 6.5 6h1.8l1.4-2h4.6l1.4 2h1.8A2.5 2.5 0 0 1 20 8.5v8a2.5 2.5 0 0 1-2.5 2.5h-11A2.5 2.5 0 0 1 4 16.5v-8Z" />
    <circle cx="12" cy="12.3" r="3.6" />
  </Svg>
);

export const WeakSignalIcon = () => (
  <Svg size={20}>
    <path d="M5 18h.01M9.5 18v-3M14 18v-6" />
    <path d="M18.5 18V9" strokeOpacity="0.35" />
  </Svg>
);

/** A phone held upright with a face inside a dashed frame: "hold the phone at eye level". */
export function FaceInFrame() {
  return (
    <svg className="art art-frame" viewBox="0 0 120 120" aria-hidden="true" focusable="false">
      <rect x="30" y="8" width="60" height="104" rx="12" fill="var(--surface)" stroke="currentColor" strokeWidth="2.5" />
      <rect x="52" y="13" width="16" height="3" rx="1.5" fill="currentColor" opacity="0.4" />
      <rect x="38" y="26" width="44" height="66" rx="22" fill="none" stroke="var(--stamp)" strokeWidth="2.5"
        strokeDasharray="5 5" />
      <ellipse cx="60" cy="54" rx="11" ry="13.5" fill="var(--stamp-tint)" stroke="currentColor" strokeWidth="2.2" />
      <path d="M43 88c3-9 9.5-13 17-13s14 4 17 13" fill="none" stroke="currentColor" strokeWidth="2.2"
        strokeLinecap="round" />
      <circle cx="55.5" cy="53" r="1.6" fill="currentColor" />
      <circle cx="64.5" cy="53" r="1.6" fill="currentColor" />
      <path d="M56.5 60.5c2.2 1.6 4.8 1.6 7 0" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

/** One icon per coaching tip. */
export function TipIcon({ tip }: { tip: CoachTip }) {
  switch (tip) {
    case "light":
      return (
        <Svg size={28}>
          <circle cx="12" cy="12" r="4" />
          <path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M5.3 18.7l1.4-1.4M17.3 6.7l1.4-1.4" />
        </Svg>
      );
    case "backlight":
      return (
        <Svg size={28}>
          <circle cx="17" cy="7" r="3" />
          <path d="M17 1.8v1M21.6 7h1M20.3 3.7l.7-.7" />
          <circle cx="9" cy="11" r="3.2" />
          <path d="M3.5 21c.8-3.6 3-5.5 5.5-5.5s4.7 1.9 5.5 5.5" />
        </Svg>
      );
    case "closer":
      return (
        <Svg size={28}>
          <circle cx="12" cy="11" r="3.4" />
          <path d="M3 8V4.5A1.5 1.5 0 0 1 4.5 3H8M16 3h3.5A1.5 1.5 0 0 1 21 4.5V8M21 16v3.5a1.5 1.5 0 0 1-1.5 1.5H16M8 21H4.5A1.5 1.5 0 0 1 3 19.5V16" />
          <path d="M7.5 19c1-2.3 2.6-3.3 4.5-3.3s3.5 1 4.5 3.3" />
        </Svg>
      );
    case "shoulders":
      return (
        <Svg size={28}>
          <circle cx="12" cy="7.5" r="3.5" />
          <path d="M3.5 20.5c.6-4.6 4-7 8.5-7s7.9 2.4 8.5 7" />
        </Svg>
      );
    case "still":
      return (
        <Svg size={28}>
          <rect x="7.5" y="4.5" width="3" height="15" rx="1.2" />
          <rect x="13.5" y="4.5" width="3" height="15" rx="1.2" />
        </Svg>
      );
  }
}

/** Result: the large tick in a circle. */
export function DoneArt() {
  return (
    <svg className="art art-result art-done" viewBox="0 0 96 96" aria-hidden="true" focusable="false">
      <circle cx="48" cy="48" r="44" fill="var(--ok-tint)" />
      <circle cx="48" cy="48" r="32" fill="var(--ok)" />
      <path d="m34 49 9.5 9.5L63 39" fill="none" stroke="var(--surface)" strokeWidth="6" strokeLinecap="round"
        strokeLinejoin="round" />
    </svg>
  );
}

/** Result: a gentle circular arrow, "once more". */
export function RetryArt() {
  return (
    <svg className="art art-result art-retry" viewBox="0 0 96 96" aria-hidden="true" focusable="false">
      <circle cx="48" cy="48" r="44" fill="var(--stamp-tint)" />
      <path d="M66 42a19 19 0 1 0 .6 11" fill="none" stroke="var(--stamp)" strokeWidth="5.5" strokeLinecap="round" />
      <path d="M68 29v14H54" fill="none" stroke="var(--stamp)" strokeWidth="5.5" strokeLinecap="round"
        strokeLinejoin="round" />
    </svg>
  );
}

/** Result: an agent with a headset, "the agent will help". */
export function AgentArt() {
  return (
    <svg className="art art-result art-agent" viewBox="0 0 96 96" aria-hidden="true" focusable="false">
      <circle cx="48" cy="48" r="44" fill="var(--stamp-tint)" />
      <g fill="none" stroke="var(--stamp)" strokeWidth="4.5" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="48" cy="42" r="10" />
        <path d="M29 72c2.5-9 10-14 19-14s16.5 5 19 14" />
        <path d="M34 44v-3a14 14 0 0 1 28 0v3" />
        <path d="M62 44v4a6 6 0 0 1-6 6h-4" />
      </g>
    </svg>
  );
}

/** Error: a calm "!" in a circle. */
export function PauseArt() {
  return (
    <svg className="art art-result art-pause" viewBox="0 0 96 96" aria-hidden="true" focusable="false">
      <circle cx="48" cy="48" r="44" fill="var(--warn-tint)" />
      <circle cx="48" cy="48" r="30" fill="none" stroke="var(--warn)" strokeWidth="5" />
      <path d="M48 34v17" stroke="var(--warn)" strokeWidth="6" strokeLinecap="round" />
      <circle cx="48" cy="62" r="3.6" fill="var(--warn)" />
    </svg>
  );
}
