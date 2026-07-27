import { useEffect } from "react";

import { useSettingsStore } from "../../features/settings/settings-store";

export function SettingsSynchronizer() {
  const language = useSettingsStore((state) => state.language);
  const theme = useSettingsStore((state) => state.theme);

  useEffect(() => {
    const root = document.documentElement;
    const systemDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const dark = theme === "dark" || (theme === "system" && systemDark);

    root.classList.toggle("dark", dark);
    root.lang = language;
    root.dir = language === "ar" ? "rtl" : "ltr";
    document.body.dir = root.dir;

    const color = dark ? "#07111f" : "#f5f8fc";
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", color);
  }, [language, theme]);

  useEffect(() => {
    if (theme !== "system") {
      return;
    }

    const query = window.matchMedia("(prefers-color-scheme: dark)");
    const listener = () => {
      document.documentElement.classList.toggle("dark", query.matches);
    };

    query.addEventListener("change", listener);
    return () => query.removeEventListener("change", listener);
  }, [theme]);

  return null;
}
