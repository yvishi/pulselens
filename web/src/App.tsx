import { lazy, Suspense } from "react";
import { Link, Route, Routes } from "react-router-dom";
import { ConsoleList } from "./console/ConsoleList";
import { ConsoleSession } from "./console/ConsoleSession";

// Final routes (docs/tasks/keshav.md K1): nobody edits them later. Customer and Lab pages belong to Yash.
const CustomerPage = lazy(() => import("./customer/CustomerPage").then((m) => ({ default: m.CustomerPage })));
const LabPage = lazy(() => import("./lab/LabPage").then((m) => ({ default: m.LabPage })));

export function Home() {
  return (
    <main className="home">
      <h1>PulseLens</h1>
      <nav aria-label="Pages">
        <ul>
          <li>
            <Link to="/console">Customer demo (from the console)</Link>
          </li>
          <li>
            <Link to="/lab">Lab recording</Link>
          </li>
          <li>
            <Link to="/console">Agent console</Link>
          </li>
        </ul>
      </nav>
    </main>
  );
}

export function App() {
  return (
    <Suspense fallback={<p className="loading">Loading…</p>}>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/customer/:sessionId" element={<CustomerPage />} />
        <Route path="/lab" element={<LabPage />} />
        <Route path="/console" element={<ConsoleList />} />
        <Route path="/console/:sessionId" element={<ConsoleSession />} />
      </Routes>
    </Suspense>
  );
}
