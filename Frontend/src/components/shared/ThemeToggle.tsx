import { Laptop, Moon, Sun } from "lucide-react";

import { useSettingsStore } from "../../features/settings/settings-store";
import { useI18n } from "../../lib/i18n";
import { IconButton } from "../ui/IconButton";

export function ThemeToggle() {
  const theme = useSettingsStore((state) => state.theme);
  const setTheme = useSettingsStore((state) => state.setTheme);
  const { t } = useI18n();

  const nextTheme = theme === "system" ? "light" : theme === "light" ? "dark" : "system";
  const icon = theme === "dark" ? <Moon size={18} /> : theme === "light" ? <Sun size={18} /> : <Laptop size={18} />;

  return (
    <IconButton label={t("theme")} onClick={() => setTheme(nextTheme)}>
      {icon}
    </IconButton>
  );
}
