import { lazy, Suspense } from "react";
import { Link, Route, Routes } from "react-router-dom";
import { ConsoleList } from "./console/ConsoleList";
import { ConsoleSession } from "./console/ConsoleSession";
import { AppShell } from "./shared/AppShell";

// Customer and Lab pages belong to Yash. The customer page sits outside the shell: no links to the console.
const CustomerPage = lazy(() => import("./customer/CustomerPage").then((m) => ({ default: m.CustomerPage })));
const LabPage = lazy(() => import("./lab/LabPage").then((m) => ({ default: m.LabPage })));

/** What an agent can do here, in plain words, one card per job. */
const TASKS = [
  {
    to: "/console",
    title: "Start a verification",
    body: "Create a link for the customer on your call. They open it on their phone and follow the screen.",
    go: "Start now",
  },
  {
    to: "/console",
    title: "Review verifications",
    body: "See every customer check, what PulseLens recommends, and record your decision.",
    go: "Open the list",
  },
  {
    to: "/lab",
    title: "Record test sessions",
    body: "For the project team: record labelled genuine and attack sessions to measure the system.",
    go: "Open the Lab",
  },
] as const;

export function Home() {
  return (
    <main className="home shell-page">
      <section className="home-hero">
        <p className="eyebrow">Video KYC liveness check</p>
        <h1>PulseLens</h1>
        <p>Checks that the person on your video call is real and present, and tells you in plain words what to do next.</p>
      </section>
      <nav aria-label="Pages">
        <ul className="home-tasks">
          {TASKS.map((t) => (
            <li key={t.title}>
              <Link to={t.to} className="home-task card">
                <h2>{t.title}</h2>
                <p>{t.body}</p>
                <span className="go" aria-hidden="true">
                  {t.go} →
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </nav>
      <section className="home-steps" aria-labelledby="how-title">
        <h2 id="how-title">How a verification works</h2>
        <ol>
          <li>Start a verification and share the link or QR code with the customer.</li>
          <li>The customer's screen shows a few soft colours and asks them to turn their head. About 20 seconds.</li>
          <li>PulseLens gives a recommendation: looks genuine, try again, or needs your review.</li>
          <li>You make the final decision: approve, ask for a new attempt, or escalate to the fraud team.</li>
        </ol>
      </section>
    </main>
  );
}

export function App() {
  return (
    <Suspense fallback={<p className="loading">Loading…</p>}>
      <Routes>
        <Route path="/customer/:sessionId" element={<CustomerPage />} />
        <Route element={<AppShell />}>
          <Route path="/" element={<Home />} />
          <Route path="/lab" element={<LabPage />} />
          <Route path="/console" element={<ConsoleList />} />
          <Route path="/console/:sessionId" element={<ConsoleSession />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </Suspense>
  );
}

function NotFound() {
  return (
    <main className="shell-page">
      <h1>This page does not exist</h1>
      <p className="muted">The link may be mistyped or out of date.</p>
      <p>
        <Link to="/" className="btn btn-primary">
          Go to the home page
        </Link>
      </p>
    </main>
  );
}
