import { AnimatePresence, motion } from "framer-motion";
import { CheckCircle2, Link2, LoaderCircle, X, XCircle } from "lucide-react";
import { useEffect, useState } from "react";

import { useSettingsStore } from "../../features/settings/settings-store";
import { testBackendConnection } from "../../lib/api";
import { normalizeUrl } from "../../lib/format";
import { useI18n } from "../../lib/i18n";
import { Button } from "../ui/Button";

interface ConnectionSettingsModalProps {
  open: boolean;
  onClose: () => void;
}

export function ConnectionSettingsModal({ open, onClose }: ConnectionSettingsModalProps) {
  const savedUrl = useSettingsStore((state) => state.apiBaseUrl);
  const setApiBaseUrl = useSettingsStore((state) => state.setApiBaseUrl);
  const setBackendState = useSettingsStore((state) => state.setBackendState);
  const { t } = useI18n();
  const [value, setValue] = useState(savedUrl);
  const [status, setStatus] = useState<"idle" | "testing" | "success" | "error">("idle");
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (open) {
      setValue(savedUrl);
      setStatus("idle");
      setMessage("");
    }
  }, [open, savedUrl]);

  useEffect(() => {
    if (!open) {
      return;
    }

    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };

    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose, open]);

  async function handleTest() {
    setStatus("testing");
    setMessage("");

    try {
      const result = await testBackendConnection(value);
      setStatus("success");
      setBackendState("online");
      setMessage(`${result.model_version} · ${result.device.toUpperCase()}`);
    } catch (error) {
      setStatus("error");
      setBackendState("offline");
      setMessage(error instanceof Error ? error.message : t("requestFailed"));
    }
  }

  function handleSave() {
    setApiBaseUrl(normalizeUrl(value));
    onClose();
  }

  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          className="fixed inset-0 z-[100] flex items-center justify-center bg-[#020711]/70 px-4 backdrop-blur-md"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onMouseDown={(event) => {
            if (event.currentTarget === event.target) {
              onClose();
            }
          }}
        >
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-labelledby="connection-dialog-title"
            className="w-full max-w-xl rounded-3xl border border-[var(--border)] bg-[var(--surface)] p-6 shadow-2xl"
            initial={{ opacity: 0, scale: 0.95, y: 18 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 18 }}
            transition={{ duration: 0.2 }}
          >
            <div className="flex items-start justify-between gap-4">
              <div className="flex gap-3">
                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-[var(--primary-soft)] text-[var(--primary)]">
                  <Link2 size={20} />
                </div>
                <div>
                  <h2 id="connection-dialog-title" className="text-lg font-bold text-[var(--text-primary)]">
                    {t("backendConnection")}
                  </h2>
                  <p className="mt-1 text-sm leading-6 text-[var(--text-secondary)]">
                    {t("connectionHelp")}
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={onClose}
                className="rounded-xl p-2 text-[var(--text-tertiary)] transition-colors hover:bg-[var(--surface-hover)] hover:text-[var(--text-primary)]"
                aria-label={t("close")}
              >
                <X size={20} />
              </button>
            </div>

            <label className="mt-6 block text-sm font-semibold text-[var(--text-primary)]" htmlFor="api-base-url">
              {t("apiUrl")}
            </label>
            <input
              id="api-base-url"
              type="url"
              value={value}
              onChange={(event) => {
                setValue(event.target.value);
                setStatus("idle");
                setMessage("");
              }}
              placeholder="https://example.trycloudflare.com"
              className="mt-2 h-12 w-full rounded-xl border border-[var(--border)] bg-[var(--surface-muted)] px-4 text-sm text-[var(--text-primary)] outline-none transition-all placeholder:text-[var(--text-tertiary)] focus:border-[var(--primary)] focus:ring-4 focus:ring-[var(--primary-soft)]"
            />

            {status !== "idle" ? (
              <div
                className={`mt-4 flex items-center gap-2 rounded-xl px-4 py-3 text-sm font-medium ${status === "success" ? "bg-[var(--success-soft)] text-[var(--success)]" : status === "error" ? "bg-[var(--danger-soft)] text-[var(--danger)]" : "bg-[var(--warning-soft)] text-[var(--warning)]"}`}
              >
                {status === "testing" ? <LoaderCircle size={17} className="animate-spin" /> : null}
                {status === "success" ? <CheckCircle2 size={17} /> : null}
                {status === "error" ? <XCircle size={17} /> : null}
                <span>{status === "testing" ? t("testConnection") : message}</span>
              </div>
            ) : null}

            <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
              <Button variant="secondary" onClick={handleTest} disabled={!value || status === "testing"}>
                {status === "testing" ? <LoaderCircle size={16} className="animate-spin" /> : null}
                {t("testConnection")}
              </Button>
              <Button onClick={handleSave} disabled={!value}>
                {t("saveConnection")}
              </Button>
            </div>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
