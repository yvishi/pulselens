// The customer flow at /customer/:sessionId?t=<token>: the shared capture screens with the default result screen.
import { useParams, useSearchParams } from "react-router-dom";
import { CaptureFlow } from "./CaptureFlow";

export function CustomerPage() {
  const { sessionId = "" } = useParams();
  const [search] = useSearchParams();
  return <CaptureFlow key={sessionId} sessionId={sessionId} token={search.get("t") ?? ""} />;
}
