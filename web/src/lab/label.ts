// The operator form's values and their validation into a contract Label (docs/CONTRACT.md section 3).
// Pseudonymous codes only (AGENTS.md rule 8): the form never asks for, nor stores, a name.
import type { Label } from "../contracts";

export const LIGHTS = ["bright", "normal", "dim", "tube"] as const satisfies readonly Label["light"][];
export const KINDS = [
  "genuine", "replay_screen", "virtual_camera", "live_swap", "photo_animation",
] as const satisfies readonly Label["kind"][];
export const SETS = ["A", "B"] as const satisfies readonly Label["set"][];

/** Plain words for each option, for the form and the handoff summary. */
export const KIND_TEXT: Record<Label["kind"], string> = {
  genuine: "Genuine (the person, live)",
  replay_screen: "Replay on a screen",
  virtual_camera: "Virtual camera",
  live_swap: "Live face swap",
  photo_animation: "Photo animation",
};

export const LIGHT_TEXT: Record<Label["light"], string> = {
  bright: "Bright (daylight, window)",
  normal: "Normal (indoor room)",
  dim: "Dim (evening, one lamp)",
  tube: "Tube light",
};

export const SET_TEXT: Record<Label["set"], string> = {
  A: "A (tuning)",
  B: "B (held-out evaluation)",
};

/** What the form holds: every field a string (selects included), before validation. */
export interface LabelForm {
  person: string;
  device: string;
  light: Label["light"];
  kind: Label["kind"];
  tool: string;
  set: Label["set"];
  consent_ref: string;
}

export type LabelField = keyof LabelForm;
export type LabelErrors = Partial<Record<LabelField, string>>;

export const EMPTY_FORM: LabelForm = {
  person: "", device: "", light: "normal", kind: "genuine", tool: "", set: "A", consent_ref: "",
};

const PERSON = /^P\d{2}$/;
const DEVICE = /^D\d{2}$/;

/** Validates the form. Codes are trimmed and upper-cased; tool is null for genuine recordings. */
export function validateLabel(form: LabelForm): { label: Label; errors: null } | { label: null; errors: LabelErrors } {
  const person = form.person.trim().toUpperCase();
  const device = form.device.trim().toUpperCase();
  const tool = form.tool.trim();
  const consent_ref = form.consent_ref.trim();
  const errors: LabelErrors = {};
  if (!PERSON.test(person)) errors.person = "Person code: P and two digits, for example P01.";
  if (!DEVICE.test(device)) errors.device = "Device code: D and two digits, for example D01.";
  if (!LIGHTS.includes(form.light)) errors.light = "Choose the light.";
  if (!KINDS.includes(form.kind)) errors.kind = "Choose the kind.";
  if (form.kind !== "genuine" && !tool) errors.tool = "Name the tool used for this attack.";
  if (!SETS.includes(form.set)) errors.set = "Choose set A or B.";
  if (!consent_ref) errors.consent_ref = "The consent reference is required.";
  if (Object.keys(errors).length) return { label: null, errors };
  return {
    label: { person, device, light: form.light, kind: form.kind, tool: form.kind === "genuine" ? null : tool, set: form.set, consent_ref },
    errors: null,
  };
}

/** The form for a Label (to prefill "Record another"). */
export function formOf(label: Label): LabelForm {
  return { ...label, tool: label.tool ?? "" };
}

const STORAGE_KEY = "pulselens.lab.lastLabel";

/** The last-used settings in this browser, or the empty form. Storage may be unavailable: never throws. */
export function loadLastForm(): LabelForm {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return EMPTY_FORM;
    const saved = JSON.parse(raw) as Partial<Record<LabelField, unknown>>;
    const form = { ...EMPTY_FORM };
    for (const key of Object.keys(EMPTY_FORM) as LabelField[]) {
      if (typeof saved[key] === "string") (form as Record<LabelField, string>)[key] = saved[key];
    }
    if (!LIGHTS.includes(form.light)) form.light = EMPTY_FORM.light;
    if (!KINDS.includes(form.kind)) form.kind = EMPTY_FORM.kind;
    if (!SETS.includes(form.set)) form.set = EMPTY_FORM.set;
    return form;
  } catch {
    return EMPTY_FORM;
  }
}

export function saveLastForm(form: LabelForm): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(form));
  } catch {
    // private window or blocked storage: the page still works, it just forgets
  }
}
