// Shared contract: the TypeScript mirror of server/pulselens/contracts.py (docs/CONTRACT.md section 4).
// Owned by Keshav. snake_case everywhere, like the wire. A pytest fails if a model or field is missing here.

export type Mode = "CAPABLE" | "CONSTRAINED" | "NO_FLASH";
export type Family = "A" | "B" | "C" | "D"; // A pulse, B sensor & stream, C light challenge, D visual & motion
export type GateStatus = "usable" | "abstain" | "protocol_error";
export type Outcome = "PASS" | "RETRY_STEP_UP" | "HUMAN_REVIEW";
export type StepUp = "fresh_challenge" | "no_flash" | "agent_checks" | "assisted_kyc";
export type SessionState = "created" | "preflight" | "capturing" | "analysing" | "done" | "expired";
export type CustomerMessage = "please_wait" | "continue" | "please_retry" | "assisted_route";
export type AgentAction = "approve" | "reverify" | "escalate";
export type Product = "savings_account" | "instant_loan";
export type Platform = "android" | "ios" | "desktop" | "unknown";
export type FamilyState = "flag" | "not_raised" | "abstained" | "not_run";
export type ThresholdSource = "provisional" | "calibrated" | "rule";
export type PlotKind = "echo" | "turn" | "cadence" | "bars";

/** Lab recordings only. Pseudonymous codes; never names. */
export interface Label {
  person: string; // ^P\d{2}$
  device: string; // ^D\d{2}$
  light: "bright" | "normal" | "dim" | "tube";
  kind: "genuine" | "replay_screen" | "virtual_camera" | "live_swap" | "photo_animation";
  tool: string | null;
  set: "A" | "B";
  consent_ref: string;
}

export interface SessionCreate {
  product?: Product;
  no_flash?: boolean;
  label?: Label | null;
  previous_session_id?: string | null;
}

export interface SessionCreated {
  session_id: string;
  nonce: string;
  customer_token: string;
  customer_url: string; // "/customer/{session_id}?t={customer_token}"
  attempt: number;
  expires_at_ms: number;
}

export interface ModeProbe {
  requested: [number, number, number]; // width, height, fps asked for
  accepted: boolean;
  delivered: [number, number] | null;
  switch_ms: number | null;
  frames_missing: number | null;
}

export interface Preflight {
  user_agent: string;
  platform: Platform;
  browser: string;
  camera_label: string;
  width: number;
  height: number;
  measured_fps: number;
  dropped_frame_ratio: number;
  blur: number;
  brightness: number;
  face_found: boolean;
  face_fraction: number;
  controls: string[];
  gyro: boolean;
  no_flash_requested: boolean;
  clock: "captureTime" | "expectedDisplayTime" | "now";
  probe: ModeProbe[];
}

export interface Plan {
  mode: Mode;
  run_light: boolean;
  run_turn: boolean;
  agent_questions: boolean;
  reasons: string[];
}

export interface ColourStep {
  kind: "colour";
  step_id: string; // "c0", "c1", ...
  hue_deg: number; // never in [345, 360) or [0, 15]
  start_offset_ms: number; // from the end of the baseline
  dwell_ms: number;
}

export interface TurnStep {
  kind: "turn";
  step_id: string; // "t0"
  direction: "left" | "right"; // the person's own left/right
  start_offset_ms: number;
  duration_ms: number;
}

export type Step = ColourStep | TurnStep;

export interface Challenge {
  session_id: string;
  nonce: string;
  mode: Mode;
  baseline_ms: number;
  steps: Step[]; // sorted by start_offset_ms
  total_ms: number;
}

export interface FrameMeta {
  idx: number;
  t_ms: number; // ms since t0
  w: number;
  h: number;
}

export interface FrameBatchMeta {
  batch_seq: number;
  frames: FrameMeta[];
}

export interface ChallengeEvent {
  step_id: string;
  status: "shown" | "skipped";
  painted_t_ms: number | null;
  ended_t_ms: number | null;
  shown_rgb: [number, number, number] | null;
  skip_reason?: string | null; // "fps_drop", "no_flash", "page_hidden"
}

export interface Plot {
  kind: PlotKind;
  series: Record<string, [number, number][]>; // name -> [(t_ms, value)], <= 300 points each
  markers?: [number, string][];
  // NEVER a pulse waveform or a heart rate.
}

export interface CheckResult {
  check_id: string;
  family: Family;
  vote_group: string;
  status: GateStatus;
  risk: number | null;
  flag: boolean;
  quality: number;
  uncertainty?: number | null;
  features?: Record<string, number>;
  reason_codes?: string[];
  explanation: string;
  window_id?: string | null;
  threshold_source: ThresholdSource;
  plot?: Plot | null;
}

export interface FamilySummary {
  family: Family;
  state: FamilyState;
  usable_checks: number;
  flagged_checks: number;
  reasons: string[];
}

export interface Decision {
  outcome: Outcome;
  step_up: StepUp | null;
  families: FamilySummary[]; // always A, B, C, D in that order
  reasons: string[];
  integrity_violation: boolean;
  provisional: boolean;
  decided_at_ms: number;
}

export interface CustomerStatus {
  state: SessionState;
  message: CustomerMessage;
}

export interface AgentDecision {
  action: AgentAction;
  note?: string;
}

export interface SessionSummary {
  session_id: string;
  created_at_ms: number;
  product: Product;
  attempt: number;
  state: SessionState;
  mode: Mode | null;
  outcome: Outcome | null;
  label_kind: string | null;
}

export interface SessionReport {
  session_id: string;
  product: Product;
  attempt: number;
  state: SessionState;
  label: Label | null;
  preflight: Preflight | null;
  plan: Plan | null;
  challenge: Challenge | null;
  events: ChallengeEvent[];
  frame_count: number;
  results: CheckResult[];
  decision: Decision | null;
  agent_decision: AgentDecision | null;
}
