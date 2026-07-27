import { Activity, CircleOff, LoaderCircle } from "lucide-react";

import { useSettingsStore } from "../../features/settings/settings-store";
import { useI18n } from "../../lib/i18n";

export function BackendStatusPill({ onClick }: { onClick?: () => void }) {
  const backendState = useSettingsStore((state) => state.backendState);
  const { t } = useI18n();

  const stateConfig = {
    online: {
      label: t("backendOnline"),
      className: "bg-[var(--success-soft)] text-[var(--success)]",
      icon: <Activity size={14} />,
    },
    warming: {
      label: t("backendWarming"),
      className: "bg-[var(--warning-soft)] text-[var(--warning)]",
      icon: <LoaderCircle size={14} className="animate-spin" />,
    },
    offline: {
      label: t("backendOffline"),
      className: "bg-[var(--danger-soft)] text-[var(--danger)]",
      icon: <CircleOff size={14} />,
    },
    unknown: {
      label: t("backendConnection"),
      className: "bg-[var(--surface-muted)] text-[var(--text-secondary)]",
      icon: <Activity size={14} />,
    },
  } as const;

  const current = stateConfig[backendState];

  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex max-w-[15rem] items-center gap-2 rounded-full px-3 py-2 text-xs font-semibold transition-transform hover:-translate-y-0.5 ${current.className}`}
      title={current.label}
    >
      {current.icon}
      <span className="hidden truncate sm:inline">{current.label}</span>
    </button>
  );
}
