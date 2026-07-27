import { useSettingsStore } from "../../features/settings/settings-store";

export function LanguageSwitch({ compact = false }: { compact?: boolean }) {
  const language = useSettingsStore((state) => state.language);
  const setLanguage = useSettingsStore((state) => state.setLanguage);

  return (
    <div
      className={`inline-flex items-center rounded-xl border border-[var(--border)] bg-[var(--surface-muted)] p-1 ${compact ? "h-9" : "h-10"}`}
      aria-label="Language switch"
    >
      {(["en", "ar"] as const).map((item) => (
        <button
          key={item}
          onClick={() => setLanguage(item)}
          className={`min-w-9 rounded-lg px-2 py-1 text-xs font-bold transition-all duration-200 ${language === item ? "bg-[var(--surface)] text-[var(--primary)] shadow-sm" : "text-[var(--text-tertiary)] hover:text-[var(--text-primary)]"}`}
          aria-pressed={language === item}
        >
          {item.toUpperCase()}
        </button>
      ))}
    </div>
  );
}
