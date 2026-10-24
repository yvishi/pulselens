// The Lab operator's form: pseudonymous codes and recording conditions, never a name (AGENTS.md rule 8).
import { useState, type FormEvent, type ReactNode } from "react";
import type { Label } from "../contracts";
import { KIND_TEXT, KINDS, LIGHT_TEXT, LIGHTS, SET_TEXT, SETS, validateLabel, type LabelErrors, type LabelField, type LabelForm } from "./label";

/** Helper text under each field (not part of the label, so the accessible name stays exactly the label). */
const HELP: Partial<Record<LabelField, string>> = {
  person: "Person code like P01 — never a name.",
  device: "Device code like D01, from the device list.",
  tool: "What made the attack, e.g. obs, deep_live_cam, phone_screen.",
  set: "A for tuning; B is kept aside to measure the final system.",
  consent_ref: "The reference on the signed consent form.",
};

interface Props {
  initial: LabelForm;
  busy: boolean;
  /** a server error from the last Continue */
  error: string | null;
  onSubmit: (label: Label, form: LabelForm) => void;
}

export function OperatorForm({ initial, busy, error, onSubmit }: Props) {
  const [form, setForm] = useState<LabelForm>(initial);
  const [errors, setErrors] = useState<LabelErrors>({});
  const set = <K extends LabelField>(key: K, value: LabelForm[K]) => setForm((f) => ({ ...f, [key]: value }));

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const r = validateLabel(form);
    setErrors(r.errors ?? {});
    if (r.label) onSubmit(r.label, form);
  };

  const field = (key: LabelField) => {
    const describedBy = [HELP[key] && `lab-${key}-help`, errors[key] && `lab-${key}-error`].filter(Boolean).join(" ");
    return {
      id: `lab-${key}`,
      "aria-invalid": errors[key] ? true : undefined,
      "aria-describedby": describedBy || undefined,
    };
  };

  /** One field: label, control, helper text, error. */
  const row = (key: LabelField, label: string, control: ReactNode) => (
    <div className={errors[key] ? "lab-row has-error" : "lab-row"}>
      <label htmlFor={`lab-${key}`}>{label}</label>
      {control}
      {HELP[key] && (
        <span id={`lab-${key}-help`} className="lab-help">
          {HELP[key]}
        </span>
      )}
      {errors[key] && (
        <span id={`lab-${key}-error`} className="lab-error">
          {errors[key]}
        </span>
      )}
    </div>
  );

  const genuine = form.kind === "genuine";

  return (
    <form className="lab-form card" onSubmit={submit} noValidate aria-labelledby="lab-title">
      <header className="lab-form-head">
        <p className="eyebrow">Project team</p>
        <h1 id="lab-title">Lab recording</h1>
        <p className="muted">Record one labelled test session. Codes only: never write a name here.</p>
      </header>

      <fieldset className="lab-group">
        <legend>Who and which phone</legend>
        <div className="lab-pair">
          {row("person", "Person code",
            <input {...field("person")} value={form.person} placeholder="P01" autoComplete="off" autoCapitalize="characters"
              onChange={(e) => set("person", e.target.value)} />)}
          {row("device", "Device code",
            <input {...field("device")} value={form.device} placeholder="D01" autoComplete="off" autoCapitalize="characters"
              onChange={(e) => set("device", e.target.value)} />)}
        </div>
      </fieldset>

      <fieldset className="lab-group">
        <legend>What is being recorded</legend>
        {row("kind", "Kind",
          <select {...field("kind")} value={form.kind} onChange={(e) => set("kind", e.target.value as Label["kind"])}>
            {KINDS.map((k) => <option key={k} value={k}>{KIND_TEXT[k]}</option>)}
          </select>)}
        {row("tool", genuine ? "Tool (not needed for genuine)" : "Tool",
          <input {...field("tool")} value={form.tool} placeholder="obs, deep_live_cam, phone_screen…" autoComplete="off"
            disabled={genuine} onChange={(e) => set("tool", e.target.value)} />)}
        {row("light", "Light",
          <select {...field("light")} value={form.light} onChange={(e) => set("light", e.target.value as Label["light"])}>
            {LIGHTS.map((l) => <option key={l} value={l}>{LIGHT_TEXT[l]}</option>)}
          </select>)}
      </fieldset>

      <fieldset className="lab-group">
        <legend>Study records</legend>
        {row("set", "Set",
          <select {...field("set")} value={form.set} onChange={(e) => set("set", e.target.value as Label["set"])}>
            {SETS.map((s) => <option key={s} value={s}>{SET_TEXT[s]}</option>)}
          </select>)}
        {row("consent_ref", "Consent reference",
          <input {...field("consent_ref")} value={form.consent_ref} placeholder="CF-2026-014" autoComplete="off"
            onChange={(e) => set("consent_ref", e.target.value)} />)}
      </fieldset>

      {error && <p className="lab-error lab-alert" role="alert">{error}</p>}
      <div className="lab-actions">
        <button type="submit" className="btn btn-primary" disabled={busy}>
          {busy ? "Creating…" : "Continue"}
        </button>
      </div>
    </form>
  );
}
