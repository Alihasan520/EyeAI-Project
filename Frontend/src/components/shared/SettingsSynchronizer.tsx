import { useEffect } from "react";

import { useSettingsStore } from "../../features/settings/settings-store";
import { normalizeUrl } from "../../lib/format";

function readApiUrlFromQuery(): string | null {
  const query = new URLSearchParams(window.location.search);
  const value = query.get("api");

  if (!value) {
    return null;
  }

  const normalized = normalizeUrl(value);

  try {
    const parsed = new URL(normalized);
    const isLocal =
      parsed.hostname === "localhost" || parsed.hostname === "127.0.0.1";

    if (parsed.protocol !== "https:" && !(parsed.protocol === "http:" && isLocal)) {
      return null;
    }

    return normalized;
  } catch {
    return null;
  }
}

function removeApiUrlFromAddressBar(): void {
  const url = new URL(window.location.href);
  url.searchParams.delete("api");

  const cleanUrl = `${url.pathname}${url.search}${url.hash}`;
  window.history.replaceState({}, document.title, cleanUrl);
}

export function SettingsSynchronizer() {
  const language = useSettingsStore((state) => state.language);
  const theme = useSettingsStore((state) => state.theme);
  const setApiBaseUrl = useSettingsStore((state) => state.setApiBaseUrl);
  const setBackendState = useSettingsStore((state) => state.setBackendState);

  useEffect(() => {
    const apiUrl = readApiUrlFromQuery();

    if (!apiUrl) {
      return;
    }

    setApiBaseUrl(apiUrl);
    setBackendState("unknown");
    removeApiUrlFromAddressBar();
  }, [setApiBaseUrl, setBackendState]);

  useEffect(() => {
    const root = document.documentElement;
    const systemDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const dark = theme === "dark" || (theme === "system" && systemDark);

    root.classList.toggle("dark", dark);
    root.lang = language;
    root.dir = language === "ar" ? "rtl" : "ltr";
    document.body.dir = root.dir;

    const color = dark ? "#07111f" : "#f5f8fc";
    document
      .querySelector('meta[name="theme-color"]')
      ?.setAttribute("content", color);
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
