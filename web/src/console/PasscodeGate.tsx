import { useId, useState, type FormEvent, type ReactNode } from "react";
import "./list.css";
import { clearPasscode, getPasscode, setPasscode } from "./passcode";

/** Asks for the agent passcode once per tab, then renders the console with it. `onUnauthorized` asks again. */
export function PasscodeGate({ children }: { children: (passcode: string, onUnauthorized: () => void) => ReactNode }) {
  const [passcode, setState] = useState<string | null>(getPasscode());
  const [draft, setDraft] = useState("");
  const [rejected, setRejected] = useState(false);
  const fieldId = useId();
  const hintId = useId();

  if (passcode) {
    return (
      <>
        {children(passcode, () => {
          clearPasscode();
          setState(null);
          setRejected(true);
        })}
      </>
    );
  }

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!draft.trim()) return;
    setPasscode(draft.trim());
    setState(draft.trim());
    setRejected(false);
  };

  return (
    <main className="console shell-page">
      <div className="gate">
        <form className="gate-card card" onSubmit={submit} aria-labelledby={`${fieldId}-title`}>
          <p className="eyebrow">Agent console</p>
          <h1 id={`${fieldId}-title`}>Sign in to the agent console</h1>
          <p className="muted">
            Here you start video KYC checks for customers on your call and see what PulseLens recommends. Your branch
            gives you the passcode.
          </p>
          <label className="gate-label" htmlFor={fieldId}>
            Agent passcode
          </label>
          <input
            id={fieldId}
            className="gate-input"
            type="password"
            autoComplete="current-password"
            value={draft}
            aria-describedby={hintId}
            aria-invalid={rejected || undefined}
            onChange={(e) => setDraft(e.target.value)}
          />
          <p id={hintId} className="gate-hint muted">
            You stay signed in until you close this tab.
          </p>
          {rejected && (
            <p role="alert" className="error gate-error">
              That passcode was not accepted. Check it and try again.
            </p>
          )}
          <button type="submit" className="btn btn-primary gate-submit">
            Open console
          </button>
        </form>
      </div>
    </main>
  );
}
