import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  BellRing,
  CheckCircle2,
  CircleAlert,
  Eye,
  ImageOff,
  LoaderCircle,
  ShieldAlert,
  TrendingUp,
  UserRound,
} from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { PageHeader } from "../components/ui/PageHeader";
import { SegmentedControl } from "../components/ui/SegmentedControl";
import { useAuthStore } from "../features/auth/auth-store";
import { acknowledgeAlert, listAlerts, listPatients, listVisits } from "../lib/api";
import { formatDate } from "../lib/format";
import { useI18n } from "../lib/i18n";
import type { TranslationKey } from "../lib/translations";
import type { AlertItem } from "../lib/types";

type AlertFilter = "all" | "open" | "reviewed";

export function AlertsPage() {
  const { t, language } = useI18n();
  const previewMode = useAuthStore((state) => state.previewMode);
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [filter, setFilter] = useState<AlertFilter>("open");
  const [patientRef, setPatientRef] = useState("");

  const patientsQuery = useQuery({
    queryKey: ["patients", "alerts"],
    queryFn: () => listPatients(),
    enabled: !previewMode,
  });
  const visitsQuery = useQuery({
    queryKey: ["visits", "alerts"],
    queryFn: () => listVisits(),
    enabled: !previewMode,
  });
  const alertsQuery = useQuery({
    queryKey: ["alerts", patientRef],
    queryFn: () => listAlerts(patientRef || undefined),
    enabled: !previewMode,
    refetchInterval: 30000,
  });

  const acknowledgeMutation = useMutation({
    mutationFn: (alertRef: string) => acknowledgeAlert(alertRef),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["alerts"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });

  const patients = patientsQuery.data || [];
  const visits = visitsQuery.data || [];
  const alerts = alertsQuery.data || [];
  const filteredAlerts = useMemo(
    () => alerts.filter((alert) => {
      if (filter === "open") return !alert.acknowledged;
      if (filter === "reviewed") return alert.acknowledged;
      return true;
    }),
    [alerts, filter],
  );

  const openCount = alerts.filter((item) => !item.acknowledged).length;
  const reviewedCount = alerts.length - openCount;

  const openAnalysis = (alert: AlertItem) => {
    const visit = visits.find((item) => item.visit.id === alert.visit_id);
    const patient = patients.find((item) => item.id === alert.patient_id);
    if (!visit || !patient) return;
    const params = new URLSearchParams({
      patient: patient.display_id,
      visit: visit.visit.display_id,
      eye: visit.visit.eye,
    });
    navigate(`/analysis?${params.toString()}`);
  };

  if (previewMode) {
    return (
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
        <PageHeader eyebrow="EyeAI Clinical Intelligence" title={t("alertsTitle")} description={t("alertsDescription")} />
        <EmptyState icon={<BellRing size={27} />} title={t("liveBackendRequired")} description={t("alertsPreviewDisabled")} />
      </motion.div>
    );
  }

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
      <PageHeader
        eyebrow="EyeAI Clinical Intelligence"
        title={t("alertsTitle")}
        description={t("alertsDescription")}
        actions={
          <div className="flex flex-wrap gap-2">
            <Badge tone={openCount ? "warning" : "success"} dot>{openCount} {t("unacknowledged")}</Badge>
            <Badge tone="neutral">{reviewedCount} {t("reviewedAlerts")}</Badge>
          </div>
        }
      />

      <Card className="mb-5 p-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <SegmentedControl
            value={filter}
            onChange={(value) => setFilter(value as AlertFilter)}
            options={[
              { value: "open", label: t("unacknowledged") },
              { value: "all", label: t("allAlerts") },
              { value: "reviewed", label: t("reviewedAlerts") },
            ]}
          />
          <label className="flex min-w-[260px] items-center gap-2 rounded-2xl border border-[var(--border)] bg-[var(--surface-muted)] px-3 py-2.5 text-sm text-[var(--text-secondary)]">
            <UserRound size={16} />
            <select
              className="min-w-0 flex-1 bg-transparent font-semibold text-[var(--text-primary)] outline-none"
              value={patientRef}
              onChange={(event) => setPatientRef(event.target.value)}
            >
              <option value="">{t("allPatients")}</option>
              {patients.map((patient) => (
                <option key={patient.id} value={patient.display_id}>
                  {patient.first_name} {patient.last_name} · {patient.display_id}
                </option>
              ))}
            </select>
          </label>
        </div>
      </Card>

      {alertsQuery.isLoading ? (
        <Card className="flex min-h-[300px] items-center justify-center p-8">
          <LoaderCircle className="animate-spin text-[var(--primary)]" size={30} />
        </Card>
      ) : filteredAlerts.length ? (
        <div className="grid gap-4 xl:grid-cols-2">
          {filteredAlerts.map((alert, index) => {
            const visit = visits.find((item) => item.visit.id === alert.visit_id);
            const patient = patients.find((item) => item.id === alert.patient_id);
            const meta = alertMeta(alert, t);
            return (
              <motion.div key={alert.id} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * 0.04 }}>
                <Card className={`overflow-hidden ${alert.acknowledged ? "opacity-75" : "border-[var(--warning)]/35"}`}>
                  <div className="flex items-start gap-4 p-5">
                    <span className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl ${meta.iconClass}`}>
                      {meta.icon}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="font-extrabold text-[var(--text-primary)]">{meta.title}</h3>
                        <Badge tone={alert.acknowledged ? "neutral" : meta.tone}>{alert.acknowledged ? t("reviewed") : meta.severity}</Badge>
                      </div>
                      <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">{alert.message}</p>
                      <div className="mt-4 grid gap-2 text-xs text-[var(--text-secondary)] sm:grid-cols-2">
                        <div><span className="font-bold text-[var(--text-primary)]">{t("patient")}:</span> {patient ? `${patient.first_name} ${patient.last_name}` : alert.patient_id}</div>
                        <div><span className="font-bold text-[var(--text-primary)]">{t("visit")}:</span> {visit?.visit.display_id || alert.visit_id}</div>
                        <div><span className="font-bold text-[var(--text-primary)]">{t("createdAt")}:</span> {formatDate(alert.created_at, language)}</div>
                        <div><span className="font-bold text-[var(--text-primary)]">ID:</span> {alert.display_id}</div>
                      </div>
                      <div className="mt-4 flex flex-wrap gap-2">
                        <Button size="sm" variant="secondary" icon={<Eye size={16} />} disabled={!visit || !patient} onClick={() => openAnalysis(alert)}>
                          {t("openAnalysis")}
                        </Button>
                        {!alert.acknowledged ? (
                          <Button
                            size="sm"
                            icon={acknowledgeMutation.isPending ? <LoaderCircle size={16} className="animate-spin" /> : <CheckCircle2 size={16} />}
                            disabled={acknowledgeMutation.isPending}
                            onClick={() => acknowledgeMutation.mutate(alert.display_id)}
                          >
                            {t("markReviewed")}
                          </Button>
                        ) : null}
                      </div>
                    </div>
                  </div>
                </Card>
              </motion.div>
            );
          })}
        </div>
      ) : (
        <Card className="flex min-h-[330px] items-center justify-center p-8">
          <EmptyState icon={<CheckCircle2 size={28} />} title={t("noAlerts")} description={t("noAlertsDescription")} />
        </Card>
      )}
    </motion.div>
  );
}

function alertMeta(alert: AlertItem, t: (key: TranslationKey) => string) {
  const type = alert.alert_type.toLowerCase();
  const severity = alert.severity.toLowerCase();
  const tone = severity === "high" || severity === "critical" ? "danger" : severity === "medium" ? "warning" : "neutral";
  const severityLabel = severity === "high" || severity === "critical" ? t("highSeverity") : severity === "medium" ? t("mediumSeverity") : t("lowSeverity");

  if (type.includes("quality")) {
    return { title: t("imageQualityAlert"), severity: severityLabel, tone: tone as "danger" | "warning" | "neutral", icon: <ImageOff size={21} />, iconClass: "bg-[var(--warning-soft)] text-[var(--warning)]" };
  }
  if (type.includes("score") || type.includes("change")) {
    return { title: t("scoreChangeAlert"), severity: severityLabel, tone: tone as "danger" | "warning" | "neutral", icon: <TrendingUp size={21} />, iconClass: "bg-[var(--ai-soft)] text-[var(--ai-accent)]" };
  }
  if (type.includes("system")) {
    return { title: t("systemAlert"), severity: severityLabel, tone: tone as "danger" | "warning" | "neutral", icon: <ShieldAlert size={21} />, iconClass: "bg-[var(--danger-soft)] text-[var(--danger)]" };
  }
  return { title: t("clinicalReviewAlert"), severity: severityLabel, tone: tone as "danger" | "warning" | "neutral", icon: <CircleAlert size={21} />, iconClass: "bg-[var(--warning-soft)] text-[var(--warning)]" };
}
