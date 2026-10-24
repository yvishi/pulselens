// The agent passcode, asked once per browser tab and kept in sessionStorage (prototype-level protection).
const KEY = "pulselens.agent_passcode";
const listeners = new Set<() => void>();

export function getPasscode(): string | null {
  try {
    return sessionStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function setPasscode(passcode: string): void {
  sessionStorage.setItem(KEY, passcode);
  listeners.forEach((l) => l());
}

export function clearPasscode(): void {
  sessionStorage.removeItem(KEY);
  listeners.forEach((l) => l());
}

/** For useSyncExternalStore: called whenever the passcode is set or cleared in this tab. */
export function subscribePasscode(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
