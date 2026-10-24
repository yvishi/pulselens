// The frame around every agent and operator page: the brand, the page links and sign out. Customer pages never get
// it (a customer must not find the console from their link).
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { clearPasscode, getPasscode } from "../console/passcode";

/** The page links, in the order an agent's day runs. */
export const NAV_LINKS = [
  { to: "/", label: "Home", end: true },
  { to: "/console", label: "Verifications", end: false },
  { to: "/lab", label: "Lab recording", end: true },
] as const;

/** A lens over a stamp: the PulseLens mark, drawn in the accent colour. */
export function BrandMark() {
  return (
    <svg className="brand-mark" viewBox="0 0 32 32" aria-hidden="true">
      <rect x="2" y="2" width="28" height="28" rx="8" fill="var(--stamp)" />
      <circle cx="16" cy="16" r="7.5" fill="none" stroke="var(--stamp-ink)" strokeWidth="2.5" />
      <path d="M9 16h3.2l1.6-3.4 2.6 6.8 1.8-3.4H23" fill="none" stroke="var(--stamp-ink)" strokeWidth="2"
        strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function AppShell() {
  const navigate = useNavigate();
  const signedIn = getPasscode() !== null;
  const signOut = () => {
    clearPasscode();
    navigate("/console", { replace: true });
    window.location.reload(); // the passcode gate reads storage once, on mount
  };

  return (
    <>
      <header className="shell-bar">
        <div className="shell-inner">
          <NavLink to="/" className="brand" aria-label="PulseLens home">
            <BrandMark />
            <span>
              PulseLens <small>video KYC desk</small>
            </span>
          </NavLink>
          <nav className="shell-nav" aria-label="Main">
            {NAV_LINKS.map((l) => (
              <NavLink key={l.to} to={l.to} end={l.end}>
                {l.label}
              </NavLink>
            ))}
          </nav>
          {signedIn && (
            <button type="button" className="btn btn-quiet" onClick={signOut}>
              Sign out
            </button>
          )}
        </div>
      </header>
      <Outlet />
    </>
  );
}
