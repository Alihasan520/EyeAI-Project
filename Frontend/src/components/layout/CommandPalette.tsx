import { AnimatePresence, motion } from "framer-motion";
import { BellRing, Bot, FileText, Microscope, Search, Stethoscope, UserRound, UsersRound, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useI18n } from "../../lib/i18n";

interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
}

export function CommandPalette({ open, onClose }: CommandPaletteProps) {
  const navigate = useNavigate();
  const { t } = useI18n();
  const [query, setQuery] = useState("");

  const actions = useMemo(
    () => [
      { label: t("patients"), path: "/patients", icon: UsersRound },
      { label: t("newVisit"), path: "/visits", icon: Stethoscope },
      { label: t("analysis"), path: "/analysis", icon: Microscope },
      { label: t("assistant"), path: "/assistant", icon: Bot },
      { label: t("alerts"), path: "/alerts", icon: BellRing },
      { label: t("reports"), path: "/reports", icon: FileText },
      { label: t("myProfile"), path: "/profile", icon: UserRound },
    ],
    [t],
  );

  const filtered = actions.filter((item) => item.label.toLowerCase().includes(query.toLowerCase()));

  useEffect(() => {
    if (!open) {
      setQuery("");
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

  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          className="fixed inset-0 z-[110] flex items-start justify-center bg-[#020711]/72 px-4 pt-[12vh] backdrop-blur-md"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onMouseDown={(event) => {
            if (event.currentTarget === event.target) onClose();
          }}
        >
          <motion.div
            className="w-full max-w-2xl overflow-hidden rounded-3xl border border-[var(--border)] bg-[var(--surface)] shadow-2xl"
            initial={{ opacity: 0, y: -18, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -18, scale: 0.97 }}
          >
            <div className="flex h-16 items-center gap-3 border-b border-[var(--border)] px-5">
              <Search size={20} className="text-[var(--primary)]" />
              <input
                autoFocus
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder={t("search")}
                className="h-full flex-1 bg-transparent text-base text-[var(--text-primary)] outline-none placeholder:text-[var(--text-tertiary)]"
              />
              <button onClick={onClose} className="rounded-xl p-2 text-[var(--text-tertiary)] hover:bg-[var(--surface-hover)]">
                <X size={18} />
              </button>
            </div>
            <div className="max-h-[56vh] overflow-y-auto p-3">
              <div className="px-2 pb-2 text-[0.68rem] font-bold uppercase tracking-[0.18em] text-[var(--text-tertiary)]">
                {t("commandPalette")}
              </div>
              {filtered.map((item) => {
                const Icon = item.icon;
                return (
                  <button
                    key={item.path}
                    onClick={() => {
                      navigate(item.path);
                      onClose();
                    }}
                    className="flex w-full items-center gap-3 rounded-2xl px-3 py-3 text-start text-sm font-semibold text-[var(--text-secondary)] transition-colors hover:bg-[var(--surface-hover)] hover:text-[var(--text-primary)]"
                  >
                    <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--primary-soft)] text-[var(--primary)]">
                      <Icon size={18} />
                    </span>
                    {item.label}
                  </button>
                );
              })}
            </div>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
