import { useEffect, useState } from "react";
import { Outlet } from "react-router-dom";

import { useSettingsStore } from "../../features/settings/settings-store";
import { useBackendHealth } from "../../hooks/use-backend-health";
import { CommandPalette } from "./CommandPalette";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";
import { ConnectionSettingsModal } from "../shared/ConnectionSettingsModal";
import { ScrollToTop } from "../shared/ScrollToTop";

export function AppShell() {
  const collapsed = useSettingsStore((state) => state.sidebarCollapsed);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [connectionOpen, setConnectionOpen] = useState(false);
  const [commandOpen, setCommandOpen] = useState(false);

  useBackendHealth(true);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setCommandOpen(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="min-h-screen bg-[var(--page-bg)] text-[var(--text-primary)]">
      <Sidebar mobileOpen={mobileOpen} onMobileClose={() => setMobileOpen(false)} />
      <div className={`min-h-screen transition-[padding] duration-300 ${collapsed ? "lg:ps-[84px]" : "lg:ps-[264px]"}`}>
        <Topbar
          onOpenMobile={() => setMobileOpen(true)}
          onOpenConnection={() => setConnectionOpen(true)}
          onOpenCommand={() => setCommandOpen(true)}
        />
        <main className="mx-auto w-full max-w-[1680px] px-4 py-5 sm:px-6 sm:py-7 xl:px-8">
          <Outlet />
        </main>
      </div>

      <ConnectionSettingsModal open={connectionOpen} onClose={() => setConnectionOpen(false)} />
      <CommandPalette open={commandOpen} onClose={() => setCommandOpen(false)} />
      <ScrollToTop />
    </div>
  );
}
