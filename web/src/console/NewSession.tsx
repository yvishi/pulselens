import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import QRCode from "qrcode";
import { createSession } from "../api/client";
import type { Product } from "../contracts";
import "./list.css";
import { PRODUCT_PLAIN } from "./plain";

/** Full customer URL: origin + the relative customer_url from SessionCreated. */
export function customerLink(origin: string, customerUrl: string): string {
  return origin + customerUrl;
}

type CopyState = "idle" | "copied" | "failed";

/**
 * The customer link with a copy button and a QR code for a phone to scan. `children` (optional) go under the
 * instructions, e.g. a button to follow the verification.
 */
export function CustomerLink({ url, children }: { url: string; children?: ReactNode }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [copied, setCopied] = useState<{ url: string; state: CopyState } | null>(null);
  const copy: CopyState = copied?.url === url ? copied.state : "idle";

  useEffect(() => {
    if (canvasRef.current) {
      QRCode.toCanvas(canvasRef.current, url, { width: 256 }).catch(() => undefined);
    }
  }, [url]);

  useEffect(() => {
    if (copy !== "copied") return;
    const t = setTimeout(() => setCopied(null), 2500);
    return () => clearTimeout(t);
  }, [copy]);

  const doCopy = async () => {
    try {
      await navigator.clipboard.writeText(url);
      setCopied({ url, state: "copied" });
    } catch {
      setCopied({ url, state: "failed" }); // no clipboard (e.g. plain http on a LAN): the agent can still select the link
    }
  };

  return (
    <div className="share next-link">
      <div className="share-text">
        <h3 className="share-title">Share with the customer</h3>
        <p className="share-say">
          Ask the customer to open this link on their phone, or to scan the code with their phone camera.
        </p>
        <p className="share-url">
          <a href={url} className="mono">
            {url}
          </a>
        </p>
        <div className="share-actions">
          <button type="button" className={`btn${copy === "copied" ? " is-copied" : ""}`} onClick={() => void doCopy()}>
            {copy === "copied" ? "Copied" : "Copy link"}
          </button>
          <span className="share-feedback" aria-live="polite">
            {copy === "copied" && <span className="visually-hidden">Link copied.</span>}
            {copy === "failed" && <span className="error">Could not copy. Select the link and copy it.</span>}
          </span>
        </div>
        {children}
      </div>
      <div className="share-qr">
        <canvas ref={canvasRef} aria-label="QR code of the customer link" role="img" />
      </div>
    </div>
  );
}

/** Agent starts a session: pick product, optionally no flash, then share the link or QR. */
export function NewSession() {
  const navigate = useNavigate();
  const [product, setProduct] = useState<Product>("savings_account");
  const [noFlash, setNoFlash] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<{ id: string; link: string } | null>(null);
  const productId = useId();
  const flashId = useId();
  const flashHintId = useId();

  const create = async () => {
    setBusy(true);
    setError(null);
    try {
      const made = await createSession({ product, no_flash: noFlash });
      setCreated({ id: made.session_id, link: customerLink(window.location.origin, made.customer_url) });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section aria-label="New session" className="start card">
      <div className="start-form">
        <h2 className="start-title">Start a verification</h2>
        <p className="muted start-lede">Make a link for the customer on your call. It works once, for this customer.</p>

        <div className="field">
          <label htmlFor={productId} className="field-label">
            What is the customer applying for?
          </label>
          <select
            id={productId}
            className="field-select"
            value={product}
            onChange={(e) => setProduct(e.target.value as Product)}
          >
            {(Object.keys(PRODUCT_PLAIN) as Product[]).map((p) => (
              <option key={p} value={p}>
                {PRODUCT_PLAIN[p]}
              </option>
            ))}
          </select>
        </div>

        <div className="check-option">
          <input
            id={flashId}
            type="checkbox"
            checked={noFlash}
            aria-describedby={flashHintId}
            onChange={(e) => setNoFlash(e.target.checked)}
          />
          <div>
            <label htmlFor={flashId} className="check-label">
              No flash
            </label>
            <p id={flashHintId} className="muted check-hint">
              For customers who are sensitive to flashing light: they will only be asked to turn their head.
            </p>
          </div>
        </div>

        <button type="button" className={`btn start-go${created ? "" : " btn-primary"}`} disabled={busy} onClick={() => void create()}>
          New session
        </button>
        {busy && (
          <p className="muted" aria-live="polite">
            Making the link…
          </p>
        )}
        {error && (
          <p role="alert" className="error">
            Could not start the verification: {error}
          </p>
        )}
      </div>

      {created && (
        <CustomerLink url={created.link}>
          {/* A button, not a link: the "New session" region keeps exactly one link (the customer's) for the e2e test. */}
          <button type="button" className="btn btn-primary share-watch" onClick={() => navigate(`/console/${created.id}`)}>
            Watch this verification <span aria-hidden="true">→</span>
          </button>
          <p className="muted share-id">
            Session <span className="mono">{created.id}</span>
          </p>
        </CustomerLink>
      )}
    </section>
  );
}
