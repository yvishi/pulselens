// The agent passcode, asked once per browser tab and kept in sessionStorage (prototype-level protection).
const KEY = "pulselens.agent_passcode";

export function getPasscode(): string | null {
  try {
    return sessionStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function setPasscode(passcode: string): void {
  sessionStorage.setItem(KEY, passcode);
}

export function clearPasscode(): void {
  sessionStorage.removeItem(KEY);
}
