import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { User } from "../../lib/types";

interface AuthState {
  accessToken: string | null;
  user: User | null;
  previewMode: boolean;
  setSession: (accessToken: string, user: User) => void;
  updateUser: (user: User) => void;
  startPreview: () => void;
  clearSession: () => void;
}

const previewUser: User = {
  id: "preview-user",
  display_id: "USR-DEMO",
  email: "demo@eyeai.local",
  full_name: "Dr. Lina Morgan",
  role: "admin",
  is_active: true,
  created_at: new Date().toISOString(),
};

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      accessToken: null,
      user: null,
      previewMode: false,
      setSession: (accessToken, user) =>
        set({ accessToken, user, previewMode: false }),
      updateUser: (user) => set({ user }),
      startPreview: () =>
        set({ accessToken: null, user: previewUser, previewMode: true }),
      clearSession: () =>
        set({ accessToken: null, user: null, previewMode: false }),
    }),
    {
      name: "eyeai-auth",
    },
  ),
);
