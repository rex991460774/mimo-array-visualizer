import { Check, Copy, Link2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api, errorMessage } from "../api/client";
import { Button, Callout, Dialog, Spinner } from "../components/ui";
import { useT } from "../i18n";
import { shareUrl } from "../state/actions";
import { useStore } from "../state/store";

const LOOPBACK = new Set(["localhost", "127.0.0.1", "::1", "[::1]"]);

/**
 * Copy text even on plain-HTTP LAN addresses, where the async clipboard API
 * is unavailable (it requires a secure context).
 */
async function copyText(text: string, input: HTMLInputElement | null): Promise<boolean> {
  if (window.isSecureContext && navigator.clipboard) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      // Fall through to the selection-based copy.
    }
  }
  if (!input) return false;
  input.focus();
  input.select();
  try {
    return document.execCommand("copy");
  } catch {
    return false;
  }
}

export function ShareDialog({ onClose }: { onClose: () => void }) {
  const t = useT();
  const project = useStore((state) => state.project)!;
  const setStatus = useStore((state) => state.setStatus);
  const [url, setUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState<boolean | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const loopback = LOOPBACK.has(window.location.hostname);

  // Snapshot the configuration as it is when the dialog opens.
  const snapshot = useRef(project);
  useEffect(() => {
    let cancelled = false;
    api.createShare(snapshot.current).then(
      (share) => !cancelled && setUrl(shareUrl(share.id)),
      (reason) => !cancelled && setError(errorMessage(reason)),
    );
    return () => {
      cancelled = true;
    };
  }, []);

  const copy = async () => {
    if (!url) return;
    const ok = await copyText(url, input.current);
    setCopied(ok);
    if (ok) setStatus("shareDialog.copied", "success");
  };

  return (
    <Dialog
      title={t("shareDialog.title")}
      onClose={onClose}
      footer={
        <>
          <span className="spacer" />
          <Button onClick={onClose}>{t("shareDialog.close")}</Button>
          <Button variant="primary" icon={copied ? <Check size={15} /> : <Copy size={15} />} disabled={!url} onClick={copy}>
            {copied ? t("shareDialog.copied") : t("shareDialog.copy")}
          </Button>
        </>
      }
    >
      <div className="section">
        <p className="subtle" style={{ margin: 0 }}>
          {t("shareDialog.hint")}
        </p>
        {error ? (
          <Callout tone="danger">{error}</Callout>
        ) : (
          <div className="share-link">
            <Link2 size={16} className="subtle" />
            {url ? (
              <input
                ref={input}
                className="input mono"
                readOnly
                value={url}
                aria-label={t("shareDialog.title")}
                onFocus={(event) => event.currentTarget.select()}
              />
            ) : (
              <span className="subtle">
                <Spinner /> {t("shareDialog.creating")}
              </span>
            )}
          </div>
        )}
        {copied === false && <Callout tone="warning">{t("shareDialog.copyFailed")}</Callout>}
        {loopback && <Callout tone="warning">{t("shareDialog.loopback", { host: window.location.host })}</Callout>}
        <p className="subtle" style={{ margin: 0, fontSize: 12 }}>
          {t("shareDialog.snapshot")}
        </p>
      </div>
    </Dialog>
  );
}
