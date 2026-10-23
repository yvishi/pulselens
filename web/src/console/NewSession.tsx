import { useEffect, useRef, useState } from "react";
import QRCode from "qrcode";
import { createSession } from "../api/client";
import type { Product } from "../contracts";

/** Full customer URL: origin + the relative customer_url from SessionCreated. */
export function customerLink(origin: string, customerUrl: string): string {
  return origin + customerUrl;
}

/** Agent starts a session: pick product, optionally no flash, then share the link or QR. */
export function NewSession() {
  const [product, setProduct] = useState<Product>("savings_account");
  const [noFlash, setNoFlash] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [link, setLink] = useState<string | null>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    if (link && canvasRef.current) {
      QRCode.toCanvas(canvasRef.current, link, { width: 256 }).catch(() => undefined);
    }
  }, [link]);

  const create = async () => {
    setBusy(true);
    setError(null);
    try {
      const created = await createSession({ product, no_flash: noFlash });
      setLink(customerLink(window.location.origin, created.customer_url));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section aria-label="New session">
      <label>
        Product
        <select value={product} onChange={(e) => setProduct(e.target.value as Product)}>
          <option value="savings_account">Savings account</option>
          <option value="instant_loan">Instant loan</option>
        </select>
      </label>
      <label>
        <input type="checkbox" checked={noFlash} onChange={(e) => setNoFlash(e.target.checked)} />
        No flash
      </label>
      <button type="button" disabled={busy} onClick={() => void create()}>
        New session
      </button>
      {link && (
        <div className="next-link">
          <a href={link}>{link}</a>
          <button type="button" onClick={() => void navigator.clipboard.writeText(link)}>
            Copy link
          </button>
          <canvas ref={canvasRef} />
        </div>
      )}
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
    </section>
  );
}
