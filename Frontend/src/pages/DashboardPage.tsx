import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  BellRing,
  Bot,
  CheckCircle2,
  CircleDashed,
  Cloud,
  FileSearch,
  Microscope,
  Plus,
  ShieldCheck,
  Sparkles,
  Stethoscope,
  UsersRound,
} from "lucide-react";
import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { useAuthStore } from "../features/auth/auth-store";
import { useSettingsStore } from "../features/settings/settings-store";
import { getAssistantStatus, getDashboard } from "../lib/api";
import { formatDate, formatNumber } from "../lib/format";
import { useI18n } from "../lib/i18n";
import type { AlertItem, AssistantStatusResponse, DashboardResponse } from "../lib/types";

const previewAlerts: AlertItem[] = [
  {
    id: "alert-1",
    display_id: "ALT-DEMO-001",
    patient_id: "PAT-DEMO-014",
    visit_id: "VIS-DEMO-2026-014",
    prediction_id: "ANA-DEMO-014",
    alert_type: "quality_warning",
    severity: "warning",
    message: "Possible image blur requires review before clinical interpretation.",
    acknowledged: false,
    created_at: new Date(Date.now() - 1000 * 60 * 36).toISOString(),
  },
  {
    id: "alert-2",
    display_id: "ALT-DEMO-002",
    patient_id: "PAT-DEMO-008",
    visit_id: "VIS-DEMO-2026-008",
    prediction_id: "ANA-DEMO-008",
    alert_type: "positive_screening",
    severity: "high",
    message: "Positive AMD screening output is ready for clinical review.",
    acknowledged: false,
    created_at: new Date(Date.now() - 1000 * 60 * 94).toISOString(),
  },
  {
    id: "alert-3",
    display_id: "ALT-DEMO-003",
    patient_id: "PAT-DEMO-003",
    visit_id: "VIS-DEMO-2026-003",
    prediction_id: "ANA-DEMO-003",
    alert_type: "score_change",
    severity: "medium",
    message: "The right-eye model score changed from the previous recorded visit.",
    acknowledged: false,
    created_at: new Date(Date.now() - 1000 * 60 * 190).toISOString(),
  },
];

const previewDashboard: DashboardResponse = {
  patients: 42,
  visits: 86,
  predictions: 73,
  unacknowledged_alerts: 3,
  recent_alerts: previewAlerts,
};

const previewAssistant: AssistantStatusResponse = {
  enabled: true,
  provider: "qwen_transformers",
  model_name: "Qwen/Qwen3-4B-Instruct-2507",
  model_loaded: true,
  rag_enabled: true,
  rag_loaded: true,
};

function StatCard({
  label,
  value,
  icon: Icon,
  tone,
  index,
}: {
  label: string;
  value: number;
  icon: typeof UsersRound;
  tone: "teal" | "indigo" | "amber" | "rose";
  index: number;
}) {
  const { language } = useI18n();
  const tones = {
    teal: "bg-[var(--primary-soft)] text-[var(--primary)]",
    indigo: "bg-[var(--ai-soft)] text-[var(--ai-accent)]",
    amber: "bg-[var(--warning-soft)] text-[var(--warning)]",
    rose: "bg-[var(--danger-soft)] text-[var(--danger)]",
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.06, duration: 0.35 }}
    >
      <Card interactive className="p-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="text-sm font-medium text-[var(--text-secondary)]">{label}</div>
            <div className="mt-3 text-3xl font-extrabold tracking-[-0.04em] text-[var(--text-primary)] tabular-nums">
              {formatNumber(value, language)}
            </div>
          </div>
          <div className={`flex h-11 w-11 items-center justify-center rounded-2xl ${tones[tone]}`}>
            <Icon size={20} />
          </div>
        </div>
        <div className="mt-5 h-1.5 overflow-hidden rounded-full bg-[var(--surface-muted)]">
          <motion.div
            className={`h-full rounded-full ${tone === "teal" ? "bg-[var(--primary)]" : tone === "indigo" ? "bg-[var(--ai-accent)]" : tone === "amber" ? "bg-[var(--warning)]" : "bg-[var(--danger)]"}`}
            initial={{ width: 0 }}
            animate={{ width: `${Math.min(92, 42 + value * 0.65)}%` }}
            transition={{ delay: 0.2 + index * 0.08, duration: 0.7 }}
          />
        </div>
      </Card>
    </motion.div>
  );
}

function statusTone(ready: boolean) {
  return ready ? "success" : "warning";
}

export function DashboardPage() {
  const navigate = useNavigate();
  const { t, language } = useI18n();
  const previewMode = useAuthStore((state) => state.previewMode);
  const user = useAuthStore((state) => state.user);
  const backendState = useSettingsStore((state) => state.backendState);

  const dashboardQuery = useQuery({
    queryKey: ["dashboard"],
    queryFn: getDashboard,
    enabled: !previewMode && backendState === "online",
  });

  const assistantQuery = useQuery({
    queryKey: ["assistant-status"],
    queryFn: getAssistantStatus,
    enabled: !previewMode && backendState === "online",
    refetchInterval: 45_000,
  });

  const dashboard = previewMode ? previewDashboard : dashboardQuery.data;
  const assistant = previewMode ? previewAssistant : assistantQuery.data;
  const alerts = dashboard?.recent_alerts ?? [];

  const chartData = useMemo(
    () => [
      { name: t("activePatients"), value: dashboard?.patients ?? 0, color: "var(--primary)" },
      { name: t("analyses"), value: dashboard?.predictions ?? 0, color: "var(--ai-accent)" },
      { name: t("pendingReviews"), value: dashboard?.unacknowledged_alerts ?? 0, color: "var(--warning)" },
    ],
    [dashboard, t],
  );

  const firstName = user?.full_name.split(" ")[0] || "Doctor";

  return (
    <div className="space-y-6 pb-10">
      <motion.section
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0 }}
        className="relative overflow-hidden rounded-3xl border border-[var(--border)] bg-[linear-gradient(135deg,var(--surface),color-mix(in_srgb,var(--primary-soft)_45%,var(--surface)),color-mix(in_srgb,var(--ai-soft)_48%,var(--surface)))] p-6 shadow-[var(--shadow-card)] sm:p-8"
      >
        <div className="pointer-events-none absolute -end-24 -top-28 h-72 w-72 rounded-full border border-[var(--primary)]/10" />
        <div className="pointer-events-none absolute -end-10 -top-10 h-44 w-44 rounded-full bg-[radial-gradient(circle,var(--ai-accent)_0%,transparent_68%)] opacity-[0.08]" />
        <div className="relative flex flex-col gap-6 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={previewMode ? "ai" : "success"} dot>
                {previewMode ? t("previewData") : t("liveData")}
              </Badge>
              <span className="text-xs text-[var(--text-tertiary)]">{t("today")}</span>
            </div>
            <h2 className="mt-4 text-2xl font-extrabold tracking-[-0.04em] text-[var(--text-primary)] sm:text-3xl">
              {language === "ar" ? `مرحبًا، د. ${firstName}` : `Good morning, Dr. ${firstName}`}
            </h2>
            <p className="mt-2 max-w-2xl text-sm leading-7 text-[var(--text-secondary)] sm:text-base">
              {t("overviewSubtitle")}
            </p>
          </div>
          <div className="flex flex-col gap-3 sm:flex-row">
            <Button variant="secondary" icon={<FileSearch size={18} />} onClick={() => navigate("/patients")}>
              {t("patients")}
            </Button>
            <Button icon={<Plus size={18} />} onClick={() => navigate("/visits")}>
              {t("newVisit")}
            </Button>
          </div>
        </div>
      </motion.section>

      {!dashboard && !previewMode ? (
        <Card className="p-6">
          <div className="flex flex-col items-center justify-center py-12 text-center">
            {dashboardQuery.isLoading ? (
              <CircleDashed size={32} className="animate-spin text-[var(--primary)]" />
            ) : (
              <Cloud size={32} className="text-[var(--danger)]" />
            )}
            <h3 className="mt-4 font-bold text-[var(--text-primary)]">
              {dashboardQuery.isLoading ? t("loading") : t("connectionRequired")}
            </h3>
          </div>
        </Card>
      ) : null}

      {dashboard ? (
        <>
          <section className="grid gap-4 sm:grid-cols-2 2xl:grid-cols-4">
            <StatCard label={t("activePatients")} value={dashboard.patients} icon={UsersRound} tone="teal" index={0} />
            <StatCard label={t("totalVisits")} value={dashboard.visits} icon={Stethoscope} tone="indigo" index={1} />
            <StatCard label={t("analyses")} value={dashboard.predictions} icon={Microscope} tone="amber" index={2} />
            <StatCard label={t("pendingReviews")} value={dashboard.unacknowledged_alerts} icon={BellRing} tone="rose" index={3} />
          </section>

          <section className="grid gap-6 2xl:grid-cols-[minmax(0,1.45fr)_minmax(350px,.75fr)]">
            <Card className="overflow-hidden">
              <div className="flex items-center justify-between border-b border-[var(--border)] px-5 py-4 sm:px-6">
                <div>
                  <h3 className="font-bold text-[var(--text-primary)]">{t("reviewQueue")}</h3>
                  <p className="mt-1 text-xs text-[var(--text-tertiary)]">{dashboard.unacknowledged_alerts} {t("pendingReviews").toLowerCase()}</p>
                </div>
                <Button size="sm" variant="ghost" onClick={() => navigate("/alerts")}>
                  {t("alerts")}
                  <ArrowUpRight size={15} />
                </Button>
              </div>

              <div className="divide-y divide-[var(--border)]">
                {alerts.length ? (
                  alerts.slice(0, 5).map((alert, index) => {
                    const isQuality = alert.alert_type.includes("quality");
                    const isScore = alert.alert_type.includes("score");
                    return (
                      <motion.div
                        key={alert.display_id || alert.id}
                        initial={{ opacity: 0, x: language === "ar" ? 12 : -12 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: 0.12 + index * 0.05 }}
                        className="group flex flex-col gap-4 px-5 py-4 transition-colors hover:bg-[var(--surface-hover)] sm:flex-row sm:items-center sm:px-6"
                      >
                        <div className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl ${isQuality ? "bg-[var(--warning-soft)] text-[var(--warning)]" : isScore ? "bg-[var(--ai-soft)] text-[var(--ai-accent)]" : "bg-[var(--danger-soft)] text-[var(--danger)]"}`}>
                          {isQuality ? <AlertTriangle size={20} /> : isScore ? <Activity size={20} /> : <ShieldCheck size={20} />}
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="text-sm font-bold text-[var(--text-primary)]">{alert.patient_id}</span>
                            <Badge tone={isQuality ? "warning" : isScore ? "ai" : "danger"}>
                              {isQuality ? t("qualityWarning") : isScore ? t("scoreChange") : t("reviewRequired")}
                            </Badge>
                          </div>
                          <p className="mt-1 line-clamp-2 text-sm leading-6 text-[var(--text-secondary)]">{alert.message}</p>
                          <div className="mt-1.5 flex items-center gap-2 text-xs text-[var(--text-tertiary)]">
                            <span>{alert.visit_id}</span>
                            <span>•</span>
                            <span>{formatDate(alert.created_at, language)}</span>
                          </div>
                        </div>
                        <Button size="sm" variant="secondary" onClick={() => navigate("/visits")}>
                          {t("openVisit")}
                        </Button>
                      </motion.div>
                    );
                  })
                ) : (
                  <div className="flex flex-col items-center justify-center px-6 py-14 text-center">
                    <CheckCircle2 size={30} className="text-[var(--success)]" />
                    <p className="mt-3 text-sm font-semibold text-[var(--text-primary)]">{t("noAlerts")}</p>
                  </div>
                )}
              </div>
            </Card>

            <Card className="p-5 sm:p-6">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h3 className="font-bold text-[var(--text-primary)]">{t("clinicalReadiness")}</h3>
                  <p className="mt-1 text-xs text-[var(--text-tertiary)]">Operational snapshot, not a clinical confidence score.</p>
                </div>
                <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-[var(--primary-soft)] text-[var(--primary)]">
                  <Sparkles size={18} />
                </span>
              </div>

              <div className="mt-5 h-52">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={chartData}
                      dataKey="value"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      innerRadius={56}
                      outerRadius={78}
                      paddingAngle={4}
                      stroke="none"
                    >
                      {chartData.map((entry) => (
                        <Cell key={entry.name} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        background: "var(--surface)",
                        border: "1px solid var(--border)",
                        borderRadius: "12px",
                        color: "var(--text-primary)",
                      }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>

              <div className="space-y-2.5">
                {chartData.map((item) => (
                  <div key={item.name} className="flex items-center justify-between gap-3 text-sm">
                    <span className="flex items-center gap-2 text-[var(--text-secondary)]">
                      <span className="h-2.5 w-2.5 rounded-full" style={{ background: item.color }} />
                      {item.name}
                    </span>
                    <span className="font-bold tabular-nums text-[var(--text-primary)]">{formatNumber(item.value, language)}</span>
                  </div>
                ))}
              </div>
            </Card>
          </section>

          <section className="grid gap-6 xl:grid-cols-2">
            <Card className="p-5 sm:p-6">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="font-bold text-[var(--text-primary)]">{t("systemStatus")}</h3>
                  <p className="mt-1 text-xs text-[var(--text-tertiary)]">Live service readiness through the Kaggle API session.</p>
                </div>
                <Badge tone={backendState === "online" ? "success" : "warning"} dot>
                  {backendState === "online" ? t("online") : t("offline")}
                </Badge>
              </div>

              <div className="mt-5 grid gap-3 sm:grid-cols-2">
                {[
                  { label: t("model"), ready: backendState === "online", icon: Microscope, detail: "retfound-run09-tta-v1" },
                  { label: t("qwen"), ready: Boolean(assistant?.model_loaded), icon: Bot, detail: assistant?.model_name?.split("/").pop() || "Qwen3 4B" },
                  { label: t("rag"), ready: Boolean(assistant?.rag_loaded), icon: FileSearch, detail: assistant?.rag_enabled ? "NICE + AAO" : "Disabled" },
                  { label: t("cloudflare"), ready: backendState === "online", icon: Cloud, detail: backendState === "online" ? "Tunnel connected" : "Check session" },
                ].map((service) => {
                  const Icon = service.icon;
                  return (
                    <div key={service.label} className="rounded-2xl border border-[var(--border)] bg-[var(--surface-muted)] p-4">
                      <div className="flex items-center justify-between gap-3">
                        <span className={`flex h-9 w-9 items-center justify-center rounded-xl ${service.ready ? "bg-[var(--success-soft)] text-[var(--success)]" : "bg-[var(--warning-soft)] text-[var(--warning)]"}`}>
                          <Icon size={17} />
                        </span>
                        <Badge tone={statusTone(service.ready)} dot>
                          {service.ready ? t("ready") : t("loading")}
                        </Badge>
                      </div>
                      <div className="mt-3 text-sm font-bold text-[var(--text-primary)]">{service.label}</div>
                      <div className="mt-1 truncate text-xs text-[var(--text-tertiary)]">{service.detail}</div>
                    </div>
                  );
                })}
              </div>
            </Card>

            <Card className="p-5 sm:p-6">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h3 className="font-bold text-[var(--text-primary)]">{t("recentActivity")}</h3>
                  <p className="mt-1 text-xs text-[var(--text-tertiary)]">Latest alert and review events.</p>
                </div>
                <Activity size={19} className="text-[var(--ai-accent)]" />
              </div>

              <div className="relative mt-5 space-y-5 before:absolute before:bottom-2 before:start-[17px] before:top-2 before:w-px before:bg-[var(--border)]">
                {alerts.length ? (
                  alerts.slice(0, 4).map((alert) => (
                    <div key={`activity-${alert.display_id}`} className="relative flex gap-4">
                      <span className="relative z-10 mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border-4 border-[var(--surface)] bg-[var(--ai-soft)] text-[var(--ai-accent)]">
                        <Activity size={14} />
                      </span>
                      <div>
                        <div className="text-sm font-semibold text-[var(--text-primary)]">{alert.message}</div>
                        <div className="mt-1 text-xs text-[var(--text-tertiary)]">{formatDate(alert.created_at, language)}</div>
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-[var(--text-tertiary)]">{t("noRecentActivity")}</p>
                )}
              </div>
            </Card>
          </section>
        </>
      ) : null}
    </div>
  );
}
