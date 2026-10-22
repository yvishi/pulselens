import { useParams } from "react-router-dom";

// Agent console: one session. Filled in by K7.
export function ConsoleSession() {
  const { sessionId } = useParams();
  return (
    <main>
      <h1>Session {sessionId}</h1>
      <p>Review arrives with K7.</p>
    </main>
  );
}
