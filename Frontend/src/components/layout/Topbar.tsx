import { Bell, ChevronDown, Menu, Search, Settings2, UserRound, UsersRound } from "lucide-react";
import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { useAuthStore } from "../../features/auth/auth-store";
import { useI18n } from "../../lib/i18n";
import type { TranslationKey } from "../../lib/translations";
import { BackendStatusPill } from "../shared/BackendStatusPill";
import { LanguageSwitch } from "../shared/LanguageSwitch";
import { ThemeToggle } from "../shared/ThemeToggle";
import { IconButton } from "../ui/IconButton";

interface TopbarProps {
  onOpenMobile: () => void;
  onOpenConnection: () => void;
  onOpenCommand: () => void;
}

function resolveRouteKey(pathname: string): TranslationKey {
  if (pathname.startsWith("/patients")) return "patients";
  if (pathname.startsWith("/visits")) return "visits";
  if (pathname.startsWith("/analysis")) return "analysis";
  if (pathname.startsWith("/assistant")) return "assistant";
  if (pathname.startsWith("/alerts")) return "alerts";
  if (pathname.startsWith("/reports")) return "reports";
  if (pathname.startsWith("/profile")) return "myProfile";
  if (pathname.startsWith("/system/users")) return "usersAndAccess";
  if (pathname.startsWith("/system")) return "system";
  return "dashboard";
}

export function Topbar({ onOpenMobile, onOpenConnection, onOpenCommand }: TopbarProps) {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const { t } = useI18n();
  const user = useAuthStore((state) => state.user);
  const previewMode = useAuthStore((state) => state.previewMode);
  const clearSession = useAuthStore((state) => state.clearSession);
  const [profileOpen, setProfileOpen] = useState(false);

  const routeKey = resolveRouteKey(pathname);
  const initials = user?.full_name
    .split(" ")
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("") || "EA";

  function go(path: string) {
    setProfileOpen(false);
    navigate(path);
  }

  return (
    <header className="sticky top-0 z-30 flex h-[76px] items-center border-b border-[var(--border)] bg-[color-mix(in_srgb,var(--page-bg)_82%,transparent)] px-4 backdrop-blur-xl sm:px-6">
      <div className="flex min-w-0 flex-1 items-center gap-3">
        <IconButton label="Open navigation" onClick={onOpenMobile} className="lg:hidden">
          <Menu size={20} />
        </IconButton>
        <div className="min-w-0">
          <h1 className="truncate text-base font-bold text-[var(--text-primary)] sm:text-lg">{t(routeKey)}</h1>
          <p className="hidden text-xs text-[var(--text-tertiary)] md:block">{t("keyboardHint")}</p>
        </div>
      </div>

      <button
        type="button"
        onClick={onOpenCommand}
        className="mx-4 hidden h-10 min-w-0 max-w-md flex-1 items-center gap-3 rounded-xl border border-[var(--border)] bg-[var(--surface-muted)] px-3 text-start text-sm text-[var(--text-tertiary)] transition-all hover:border-[var(--primary)]/35 hover:bg-[var(--surface-hover)] md:flex"
      >
        <Search size={17} />
        <span className="truncate">{t("search")}</span>
        <kbd className="ms-auto rounded-md border border-[var(--border)] bg-[var(--surface)] px-1.5 py-0.5 text-[0.65rem] font-semibold">Ctrl K</kbd>
      </button>

      <div className="flex items-center gap-1.5 sm:gap-2">
        <BackendStatusPill onClick={onOpenConnection} />
        <LanguageSwitch compact />
        <ThemeToggle />
        <IconButton label={t("alerts")} className="hidden sm:inline-flex" onClick={() => navigate("/alerts")}>
          <Bell size={18} />
        </IconButton>

        <div className="relative">
          <button
            type="button"
            onClick={() => setProfileOpen((value) => !value)}
            className="flex h-11 items-center gap-2 rounded-xl border border-transparent px-1.5 transition-colors hover:border-[var(--border)] hover:bg-[var(--surface-hover)]"
            aria-expanded={profileOpen}
          >
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-[linear-gradient(135deg,var(--primary),var(--ai-accent))] text-xs font-extrabold text-white">
              {initials}
            </span>
            <span className="hidden max-w-32 text-start lg:block">
              <span className="block truncate text-xs font-bold text-[var(--text-primary)]">{user?.full_name}</span>
              <span className="block truncate text-[0.68rem] text-[var(--text-tertiary)]">
                {previewMode ? t("preview") : user?.role === "admin" ? t("roleAdmin") : t("roleClinician")}
              </span>
            </span>
            <ChevronDown size={15} className="hidden text-[var(--text-tertiary)] lg:block" />
          </button>

          {profileOpen ? (
            <div className="absolute end-0 top-[calc(100%+10px)] w-64 rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-2 shadow-2xl">
              <div className="border-b border-[var(--border)] px-3 py-2">
                <div className="truncate text-sm font-bold text-[var(--text-primary)]">{user?.full_name}</div>
                <div className="mt-0.5 truncate text-xs text-[var(--text-tertiary)]">{user?.email}</div>
              </div>
              <button
                type="button"
                onClick={() => go("/profile")}
                className="mt-1 flex w-full items-center gap-2 rounded-xl px-3 py-2 text-sm font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-hover)] hover:text-[var(--text-primary)]"
              >
                <UserRound size={16} />
                {t("myProfile")}
              </button>
              {user?.role === "admin" ? (
                <button
                  type="button"
                  onClick={() => go("/system/users")}
                  className="mt-1 flex w-full items-center gap-2 rounded-xl px-3 py-2 text-sm font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-hover)] hover:text-[var(--text-primary)]"
                >
                  <UsersRound size={16} />
                  {t("usersAndAccess")}
                </button>
              ) : null}
              <button
                type="button"
                onClick={() => {
                  setProfileOpen(false);
                  onOpenConnection();
                }}
                className="mt-1 flex w-full items-center gap-2 rounded-xl px-3 py-2 text-sm font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-hover)] hover:text-[var(--text-primary)]"
              >
                <Settings2 size={16} />
                {t("openSettings")}
              </button>
              <button
                type="button"
                onClick={clearSession}
                className="mt-1 flex w-full items-center gap-2 rounded-xl px-3 py-2 text-sm font-medium text-[var(--danger)] hover:bg-[var(--danger-soft)]"
              >
                <span aria-hidden="true">↪</span>
                {t("logout")}
              </button>
            </div>
          ) : null}
        </div>
      </div>
    </header>
  );
}
