// The Lab operator's form: pseudonymous codes and recording conditions, never a name (AGENTS.md rule 8).
import { useState, type FormEvent } from "react";
import type { Label } from "../contracts";
import { KINDS, LIGHTS, SETS, validateLabel, type LabelErrors, type LabelField, type LabelForm } from "./label";

const KIND_TEXT: Record<Label["kind"], string> = {
  genuine: "Genuine (the person, live)",
  replay_screen: "Replay on a screen",
  virtual_camera: "Virtual camera",
  live_swap: "Live face swap",
  photo_animation: "Photo animation",
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

  const field = (key: LabelField) => ({
    id: `lab-${key}`,
    "aria-invalid": errors[key] ? true : undefined,
    "aria-describedby": errors[key] ? `lab-${key}-error` : undefined,
  });
  const err = (key: LabelField) =>
    errors[key] && (
      <span id={`lab-${key}-error`} className="lab-error">
        {errors[key]}
      </span>
    );

  return (
    <form className="lab-form" onSubmit={submit} noValidate aria-labelledby="lab-title">
      <h1 id="lab-title">Lab recording</h1>
      <p className="muted">Codes only. Never write a name here.</p>

      <div className="lab-row">
        <label htmlFor="lab-person">Person code</label>
        <input {...field("person")} value={form.person} placeholder="P01" autoComplete="off" autoCapitalize="characters"
          onChange={(e) => set("person", e.target.value)} />
        {err("person")}
      </div>
      <div className="lab-row">
        <label htmlFor="lab-device">Device code</label>
        <input {...field("device")} value={form.device} placeholder="D01" autoComplete="off" autoCapitalize="characters"
          onChange={(e) => set("device", e.target.value)} />
        {err("device")}
      </div>
      <div className="lab-row">
        <label htmlFor="lab-light">Light</label>
        <select {...field("light")} value={form.light} onChange={(e) => set("light", e.target.value as Label["light"])}>
          {LIGHTS.map((l) => <option key={l} value={l}>{l}</option>)}
        </select>
        {err("light")}
      </div>
      <div className="lab-row">
        <label htmlFor="lab-kind">Kind</label>
        <select {...field("kind")} value={form.kind} onChange={(e) => set("kind", e.target.value as Label["kind"])}>
          {KINDS.map((k) => <option key={k} value={k}>{KIND_TEXT[k]}</option>)}
        </select>
        {err("kind")}
      </div>
      <div className="lab-row">
        <label htmlFor="lab-tool">Tool{form.kind === "genuine" ? " (not needed for genuine)" : ""}</label>
        <input {...field("tool")} value={form.tool} placeholder="obs, deep_live_cam, phone_screen…" autoComplete="off"
          disabled={form.kind === "genuine"} onChange={(e) => set("tool", e.target.value)} />
        {err("tool")}
      </div>
      <div className="lab-row">
        <label htmlFor="lab-set">Set</label>
        <select {...field("set")} value={form.set} onChange={(e) => set("set", e.target.value as Label["set"])}>
          {SETS.map((s) => <option key={s} value={s}>{s === "A" ? "A (tuning)" : "B (held-out evaluation)"}</option>)}
        </select>
        {err("set")}
      </div>
      <div className="lab-row">
        <label htmlFor="lab-consent_ref">Consent reference</label>
        <input {...field("consent_ref")} value={form.consent_ref} placeholder="the signed form's reference" autoComplete="off"
          onChange={(e) => set("consent_ref", e.target.value)} />
        {err("consent_ref")}
      </div>

      {error && <p className="lab-error" role="alert">{error}</p>}
      <div className="actions">
        <button type="submit" className="primary" disabled={busy}>
          {busy ? "Creating…" : "Continue"}
        </button>
      </div>
    </form>
  );
}
