import { create } from "zustand";
import { persist } from "zustand/middleware";

import { DEFAULT_API_URL } from "../../lib/runtime";
import type { BackendState, Language, ThemeMode } from "../../lib/types";

interface SettingsState {
  language: Language;
  theme: ThemeMode;
  apiBaseUrl: string;
  backendState: BackendState;
  sidebarCollapsed: boolean;
  setLanguage: (language: Language) => void;
  setTheme: (theme: ThemeMode) => void;
  setApiBaseUrl: (apiBaseUrl: string) => void;
  setBackendState: (backendState: BackendState) => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  toggleSidebar: () => void;
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      language: "en",
      theme: "system",
      apiBaseUrl: DEFAULT_API_URL,
      backendState: "unknown",
      sidebarCollapsed: false,
      setLanguage: (language) => set({ language }),
      setTheme: (theme) => set({ theme }),
      setApiBaseUrl: (apiBaseUrl) => set({ apiBaseUrl }),
      setBackendState: (backendState) => set({ backendState }),
      setSidebarCollapsed: (sidebarCollapsed) => set({ sidebarCollapsed }),
      toggleSidebar: () =>
        set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
    }),
    {
      name: "eyeai-settings",
      partialize: (state) => ({
        language: state.language,
        theme: state.theme,
        apiBaseUrl: state.apiBaseUrl,
        sidebarCollapsed: state.sidebarCollapsed,
      }),
    },
  ),
);
