import { AnimatePresence, motion } from "framer-motion";
import {
  Activity,
  BellRing,
  Bot,
  ChartNoAxesCombined,
  FileText,
  Microscope,
  PanelLeftClose,
  PanelLeftOpen,
  Settings,
  Stethoscope,
  UsersRound,
  UserRound,
  X,
} from "lucide-react";
import { NavLink } from "react-router-dom";

import { useSettingsStore } from "../../features/settings/settings-store";
import { useI18n } from "../../lib/i18n";
import { EyeAILogo } from "../brand/EyeAILogo";

interface SidebarProps {
  mobileOpen: boolean;
  onMobileClose: () => void;
}

const navItems = [
  { to: "/", key: "dashboard", icon: ChartNoAxesCombined, end: true },
  { to: "/patients", end: false, key: "patients", icon: UsersRound },
  { to: "/visits", end: false, key: "visits", icon: Stethoscope },
  { to: "/analysis", end: false, key: "analysis", icon: Microscope },
  { to: "/assistant", end: false, key: "assistant", icon: Bot },
  { to: "/alerts", end: false, key: "alerts", icon: BellRing },
  { to: "/reports", end: false, key: "reports", icon: FileText },
  { to: "/profile", end: false, key: "myProfile", icon: UserRound },
  { to: "/system", end: false, key: "system", icon: Settings },
] as const;

function SidebarBody({ onNavigate }: { onNavigate?: () => void }) {
  const collapsed = useSettingsStore((state) => state.sidebarCollapsed);
  const toggleSidebar = useSettingsStore((state) => state.toggleSidebar);
  const { t } = useI18n();

  return (
    <div className="flex h-full flex-col">
      <div className={`flex h-[76px] items-center border-b border-[var(--border)] px-4 ${collapsed ? "justify-center" : "justify-between"}`}>
        <EyeAILogo compact={collapsed} />
        {!collapsed ? (
          <button
            type="button"
            onClick={toggleSidebar}
            className="hidden rounded-xl p-2 text-[var(--text-tertiary)] transition-colors hover:bg-[var(--surface-hover)] hover:text-[var(--text-primary)] lg:block"
            aria-label="Collapse sidebar"
          >
            <PanelLeftClose size={18} />
          </button>
        ) : null}
      </div>

      <nav className="flex-1 overflow-y-auto px-3 py-5">
        <div className="space-y-1.5">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                onClick={onNavigate}
                className={({ isActive }) =>
                  `group relative flex h-11 items-center rounded-xl transition-all duration-200 ${collapsed ? "justify-center px-2" : "gap-3 px-3"} ${isActive ? "bg-[linear-gradient(135deg,var(--primary-soft),var(--ai-soft))] text-[var(--primary)]" : "text-[var(--text-secondary)] hover:bg-[var(--surface-hover)] hover:text-[var(--text-primary)]"}`
                }
              >
                {({ isActive }) => (
                  <>
                    {isActive ? (
                      <motion.span
                        layoutId="sidebar-active-indicator"
                        className="absolute inset-y-2 start-0 w-1 rounded-e-full bg-[linear-gradient(180deg,var(--primary),var(--ai-accent))]"
                      />
                    ) : null}
                    <Icon size={19} strokeWidth={1.9} />
                    {!collapsed ? <span className="text-sm font-semibold">{t(item.key)}</span> : null}
                    {collapsed ? (
                      <span className="pointer-events-none absolute start-[calc(100%+10px)] z-50 hidden whitespace-nowrap rounded-lg bg-[#081321] px-2.5 py-1.5 text-xs font-semibold text-white shadow-xl group-hover:block">
                        {t(item.key)}
                      </span>
                    ) : null}
                  </>
                )}
              </NavLink>
            );
          })}
        </div>
      </nav>

      <div className="border-t border-[var(--border)] p-3">
        <div className={`rounded-2xl border border-[var(--border)] bg-[var(--surface-muted)] ${collapsed ? "p-2" : "p-3"}`}>
          <div className={`flex items-center ${collapsed ? "justify-center" : "gap-3"}`}>
            <div className="relative flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[linear-gradient(135deg,var(--primary),var(--ai-accent))] text-white">
              <Activity size={17} />
              <span className="absolute -end-1 -top-1 h-2.5 w-2.5 rounded-full border-2 border-[var(--surface-muted)] bg-[var(--success)]" />
            </div>
            {!collapsed ? (
              <div className="min-w-0">
                <div className="truncate text-xs font-bold text-[var(--text-primary)]">EyeAI Engine</div>
                <div className="mt-0.5 text-[0.68rem] text-[var(--text-tertiary)]">Clinical services</div>
              </div>
            ) : null}
          </div>
        </div>
        {collapsed ? (
          <button
            type="button"
            onClick={toggleSidebar}
            className="mt-2 hidden w-full items-center justify-center rounded-xl p-2 text-[var(--text-tertiary)] transition-colors hover:bg-[var(--surface-hover)] hover:text-[var(--text-primary)] lg:flex"
            aria-label="Expand sidebar"
          >
            <PanelLeftOpen size={18} />
          </button>
        ) : null}
      </div>
    </div>
  );
}

export function Sidebar({ mobileOpen, onMobileClose }: SidebarProps) {
  const collapsed = useSettingsStore((state) => state.sidebarCollapsed);
  const language = useSettingsStore((state) => state.language);

  return (
    <>
      <aside
        className={`fixed inset-y-0 start-0 z-40 hidden border-e border-[var(--border)] bg-[color-mix(in_srgb,var(--surface)_92%,transparent)] backdrop-blur-xl transition-[width] duration-300 lg:block ${collapsed ? "w-[84px]" : "w-[264px]"}`}
      >
        <SidebarBody />
      </aside>

      <AnimatePresence>
        {mobileOpen ? (
          <motion.div
            className="fixed inset-0 z-[80] bg-[#020711]/68 backdrop-blur-sm lg:hidden"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onMobileClose}
          >
            <motion.aside
              className={`h-full w-[min(86vw,310px)] border-[var(--border)] bg-[var(--surface)] shadow-2xl ${language === "ar" ? "ms-auto border-s" : "border-e"}`}
              initial={{ x: language === "ar" ? "100%" : "-100%" }}
              animate={{ x: 0 }}
              exit={{ x: language === "ar" ? "100%" : "-100%" }}
              transition={{ type: "spring", stiffness: 320, damping: 32 }}
              onClick={(event) => event.stopPropagation()}
            >
              <button
                type="button"
                className="absolute end-3 top-4 rounded-xl p-2 text-[var(--text-tertiary)] hover:bg-[var(--surface-hover)] hover:text-[var(--text-primary)]"
                onClick={onMobileClose}
                aria-label="Close navigation"
              >
                <X size={20} />
              </button>
              <SidebarBody onNavigate={onMobileClose} />
            </motion.aside>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </>
  );
}
