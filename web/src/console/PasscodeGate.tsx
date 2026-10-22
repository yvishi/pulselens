import { useState, type FormEvent, type ReactNode } from "react";
import { clearPasscode, getPasscode, setPasscode } from "./passcode";

/** Asks for the agent passcode once per tab, then renders the console with it. `onUnauthorized` asks again. */
export function PasscodeGate({ children }: { children: (passcode: string, onUnauthorized: () => void) => ReactNode }) {
  const [passcode, setState] = useState<string | null>(getPasscode());
  const [draft, setDraft] = useState("");
  const [rejected, setRejected] = useState(false);

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
    <main className="console">
      <h1>Agent console</h1>
      <form className="passcode" onSubmit={submit}>
        <label>
          Agent passcode
          <input type="password" autoComplete="current-password" value={draft} onChange={(e) => setDraft(e.target.value)} />
        </label>
        <button type="submit">Open console</button>
        {rejected && (
          <p role="alert" className="error">
            That passcode was not accepted.
          </p>
        )}
      </form>
    </main>
  );
}
