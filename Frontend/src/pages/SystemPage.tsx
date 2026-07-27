import { KeyRound, Settings2, ShieldCheck, UsersRound } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { useAuthStore } from "../features/auth/auth-store";
import { useI18n } from "../lib/i18n";
import { FRONTEND_VERSION } from "../lib/runtime";

export function SystemPage() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const user = useAuthStore((state) => state.user);

  const items = [
    { title: t("myProfile"), description: t("myProfileDescription"), icon: KeyRound, path: "/profile", visible: true },
    { title: t("usersAndAccess"), description: t("usersAndAccessDescription"), icon: UsersRound, path: "/system/users", visible: user?.role === "admin" },
    { title: t("connectionAndRuntime"), description: t("connectionAndRuntimeDescription"), icon: Settings2, path: "/", visible: true },
  ].filter((item) => item.visible);

  return (
    <div>
      <PageHeader eyebrow={t("workspaceAdministration")} title={t("system")} description={t("systemDescription")} />
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {items.map((item) => {
          const Icon = item.icon;
          return <button type="button" key={item.title} onClick={() => navigate(item.path)} className="text-start"><Card interactive className="h-full p-5"><div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[linear-gradient(135deg,var(--primary-soft),var(--ai-soft))] text-[var(--primary)]"><Icon size={22} /></div><h3 className="mt-5 text-lg font-extrabold text-[var(--text-primary)]">{item.title}</h3><p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">{item.description}</p><div className="mt-5 inline-flex items-center gap-2 text-xs font-bold text-[var(--primary)]"><ShieldCheck size={15} />{t("openModule")}</div></Card></button>;
        })}
      </div>
      <div className="mt-6 text-center text-xs font-semibold text-[var(--text-tertiary)]">
        {t("frontendVersion")}: {FRONTEND_VERSION}
      </div>
    </div>
  );
}
