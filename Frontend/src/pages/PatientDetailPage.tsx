import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  Activity,
  ArrowLeft,
  CalendarDays,
  Edit3,
  Eye,
  FileText,
  IdCard,
  Phone,
  Plus,
  TrendingDown,
  TrendingUp,
  UserRound,
} from "lucide-react";
import { type ReactNode, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { PatientFormModal } from "../components/patients/PatientFormModal";
import { VisitFormModal } from "../components/patients/VisitFormModal";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { SegmentedControl } from "../components/ui/SegmentedControl";
import { useAuthStore } from "../features/auth/auth-store";
import { getPatient, getTimeline } from "../lib/api";
import { formatDate } from "../lib/format";
import { useI18n } from "../lib/i18n";
import { previewPatients, previewTimeline } from "../lib/preview-data";
import type { EyeSide, TimelineEntry } from "../lib/types";

export function PatientDetailPage() {
  const { patientRef = "" } = useParams();
  const { t, language } = useI18n();
  const navigate = useNavigate();
  const previewMode = useAuthStore((state) => state.previewMode);
  const [eye, setEye] = useState<EyeSide>("right");
  const [editOpen, setEditOpen] = useState(false);
  const [visitOpen, setVisitOpen] = useState(false);

  const patientQuery = useQuery({
    queryKey: ["patient", patientRef],
    queryFn: () => getPatient(patientRef),
    enabled: !previewMode && Boolean(patientRef),
  });
  const timelineQuery = useQuery({
    queryKey: ["timeline", patientRef, eye],
    queryFn: () => getTimeline(patientRef, eye),
    enabled: !previewMode && Boolean(patientRef),
  });

  const patient = previewMode
    ? previewPatients.find((item) => item.display_id === patientRef) || previewPatients[0]
    : patientQuery.data;
  const timeline = useMemo(() => {
    if (!previewMode) return timelineQuery.data || [];
    return patient?.display_id === previewPatients[0].display_id
      ? previewTimeline.filter((entry) => entry.visit.eye === eye)
      : [];
  }, [eye, patient?.display_id, previewMode, timelineQuery.data]);

  if ((patientQuery.isLoading || timelineQuery.isLoading) && !previewMode) {
    return <div className="space-y-5"><div className="h-48 animate-pulse rounded-3xl bg-[var(--surface-muted)]" /><div className="h-96 animate-pulse rounded-3xl bg-[var(--surface-muted)]" /></div>;
  }

  if (!patient) {
    return (
      <EmptyState
        icon={<UserRound size={25} />}
        title={t("patientNotFound")}
        description={t("patientNotFoundDescription")}
        action={<Button variant="secondary" onClick={() => navigate("/patients")}>{t("patients")}</Button>}
      />
    );
  }

  const fullName = `${patient.first_name} ${patient.last_name}`;
  const latest = timeline[timeline.length - 1];

  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
      <button
        type="button"
        onClick={() => navigate("/patients")}
        className="mb-4 inline-flex items-center gap-2 text-sm font-semibold text-[var(--text-secondary)] transition-colors hover:text-[var(--primary)]"
      >
        <ArrowLeft size={17} className={language === "ar" ? "rotate-180" : ""} />
        {t("backToPatients")}
      </button>

      <Card className="relative overflow-hidden p-5 sm:p-7">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_92%_0%,var(--ai-soft),transparent_34%),radial-gradient(circle_at_0%_100%,var(--primary-soft),transparent_32%)]" />
        <div className="relative flex flex-col gap-6 xl:flex-row xl:items-center xl:justify-between">
          <div className="flex min-w-0 items-start gap-4">
            <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-3xl bg-[linear-gradient(135deg,var(--primary),var(--ai-accent))] text-lg font-extrabold text-white shadow-[0_20px_50px_-25px_var(--primary)]">
              {(patient.first_name[0] || "") + (patient.last_name[0] || "")}
            </div>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-2xl font-extrabold tracking-[-0.035em] text-[var(--text-primary)] sm:text-3xl">{fullName}</h2>
                <Badge tone="primary">{patient.display_id}</Badge>
              </div>
              <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2 text-sm text-[var(--text-secondary)]">
                <span className="inline-flex items-center gap-2"><IdCard size={15} />{patient.medical_record_number}</span>
                <span className="inline-flex items-center gap-2"><CalendarDays size={15} />{patient.date_of_birth || "—"}</span>
                <span className="inline-flex items-center gap-2"><Phone size={15} />{patient.phone || t("noPhone")}</span>
              </div>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" icon={<Edit3 size={17} />} onClick={() => setEditOpen(true)} disabled={previewMode}>{t("editPatient")}</Button>
            <Button icon={<Plus size={17} />} onClick={() => setVisitOpen(true)} disabled={previewMode}>{t("newVisit")}</Button>
          </div>
        </div>

        <div className="relative mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <Summary label={t("selectedEye")} value={eye === "right" ? t("rightEye") : t("leftEye")} icon={<Eye size={17} />} />
          <Summary label={t("recordedVisits")} value={String(timeline.length)} icon={<CalendarDays size={17} />} />
          <Summary label={t("latestModelScore")} value={latest?.prediction ? latest.prediction.probability.toFixed(4) : "—"} icon={<Activity size={17} />} />
          <Summary label={t("latestReviewStatus")} value={latest?.prediction?.quality_status || t("notAnalyzed")} icon={<FileText size={17} />} />
        </div>
      </Card>

      <div className="mt-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className="text-xl font-extrabold tracking-[-0.02em] text-[var(--text-primary)]">{t("clinicalTimeline")}</h3>
          <p className="mt-1 text-sm text-[var(--text-secondary)]">{t("clinicalTimelineDescription")}</p>
        </div>
        <SegmentedControl
          value={eye}
          options={[
            { value: "right", label: t("rightEye") },
            { value: "left", label: t("leftEye") },
          ]}
          onChange={setEye}
        />
      </div>

      <div className="mt-5">
        {timeline.length ? (
          <div className="relative space-y-5 ps-8 before:absolute before:bottom-8 before:start-[11px] before:top-8 before:w-px before:bg-[linear-gradient(180deg,var(--primary),var(--ai-accent),var(--border))]">
            {[...timeline].reverse().map((entry, index) => (
              <TimelineCard key={entry.visit.id} entry={entry} index={index} />
            ))}
          </div>
        ) : (
          <EmptyState
            icon={<CalendarDays size={25} />}
            title={t("noVisitsForEye")}
            description={t("noVisitsForEyeDescription")}
            action={!previewMode ? <Button icon={<Plus size={17} />} onClick={() => setVisitOpen(true)}>{t("createVisit")}</Button> : undefined}
          />
        )}
      </div>

      {patient.notes ? (
        <Card className="mt-6 p-5">
          <div className="flex items-center gap-2 font-bold text-[var(--text-primary)]"><FileText size={18} className="text-[var(--primary)]" />{t("patientNotes")}</div>
          <p className="mt-3 text-sm leading-7 text-[var(--text-secondary)]">{patient.notes}</p>
        </Card>
      ) : null}

      <PatientFormModal open={editOpen} onClose={() => setEditOpen(false)} patient={patient} />
      <VisitFormModal open={visitOpen} onClose={() => setVisitOpen(false)} patientRef={patient.display_id} patientName={fullName} />
    </motion.div>
  );
}

function Summary({ label, value, icon }: { label: string; value: string; icon: ReactNode }) {
  return (
    <div className="rounded-2xl border border-[var(--border)] bg-[color-mix(in_srgb,var(--surface-muted)_82%,transparent)] p-4 backdrop-blur-sm">
      <div className="flex items-center gap-2 text-xs font-semibold text-[var(--text-tertiary)]">{icon}{label}</div>
      <div className="mt-2 truncate text-sm font-extrabold text-[var(--text-primary)]">{value}</div>
    </div>
  );
}

function TimelineCard({ entry, index }: { entry: TimelineEntry; index: number }) {
  const { t, language } = useI18n();
  const navigate = useNavigate();
  const prediction = entry.prediction;
  const trendIcon = entry.trend === "increasing" ? <TrendingUp size={16} /> : entry.trend === "decreasing" ? <TrendingDown size={16} /> : <Activity size={16} />;
  const trendTone = entry.trend === "increasing" ? "warning" : entry.trend === "decreasing" ? "success" : "neutral";

  return (
    <motion.div initial={{ opacity: 0, x: language === "ar" ? 12 : -12 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: Math.min(index * 0.06, 0.3) }} className="relative">
      <span className="absolute -start-[29px] top-7 h-3.5 w-3.5 rounded-full border-[3px] border-[var(--page-bg)] bg-[var(--primary)] shadow-[0_0_0_4px_var(--primary-soft)]" />
      <Card interactive className="p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-extrabold text-[var(--text-primary)]">{entry.visit.display_id}</span>
              <Badge tone="primary">{entry.visit.eye === "right" ? t("rightEye") : t("leftEye")}</Badge>
              <Badge tone={trendTone as "neutral" | "success" | "warning"}>
                <span className="inline-flex items-center gap-1.5">{trendIcon}{t(entry.trend === "first_measurement" ? "firstMeasurement" : entry.trend)}</span>
              </Badge>
            </div>
            <div className="mt-2 text-xs text-[var(--text-tertiary)]">{formatDate(entry.visit.visit_date, language)}</div>
          </div>
          {prediction ? (
            <div className="flex flex-wrap items-center gap-3">
              <div className="rounded-xl bg-[var(--surface-muted)] px-4 py-2 text-center">
                <div className="text-[0.65rem] font-bold uppercase tracking-wider text-[var(--text-tertiary)]">{t("modelScore")}</div>
                <div className="mt-1 font-mono text-lg font-extrabold tabular-nums text-[var(--text-primary)]">{prediction.probability.toFixed(4)}</div>
              </div>
              <Badge tone={prediction.decision ? "danger" : "success"}>{prediction.label}</Badge>
            </div>
          ) : <Badge tone="neutral">{t("notAnalyzed")}</Badge>}
        </div>

        {prediction ? (
          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            <Metric label={t("decisionThreshold")} value={prediction.threshold.toFixed(3)} />
            <Metric label={t("imageQuality")} value={prediction.quality_status} />
            <Metric label={t("scoreDelta")} value={entry.score_delta == null ? "—" : `${entry.score_delta >= 0 ? "+" : ""}${entry.score_delta.toFixed(4)}`} />
          </div>
        ) : null}

        {entry.visit.notes ? <p className="mt-4 rounded-xl bg-[var(--surface-muted)] px-4 py-3 text-sm leading-6 text-[var(--text-secondary)]">{entry.visit.notes}</p> : null}
        {entry.doctor_notes.length ? (
          <div className="mt-4 border-t border-[var(--border)] pt-4">
            <div className="text-xs font-bold text-[var(--text-tertiary)]">{t("doctorNotes")}</div>
            {entry.doctor_notes.map((note) => <p key={note.id} className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">{note.text}</p>)}
          </div>
        ) : null}

        <div className="mt-4 flex justify-end">
          <Button size="sm" variant="secondary" onClick={() => navigate(`/analysis?visit=${encodeURIComponent(entry.visit.display_id)}`)}>{prediction ? t("openAnalysis") : t("analyzeVisit")}</Button>
        </div>
      </Card>
    </motion.div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="rounded-xl border border-[var(--border)] p-3"><div className="text-[0.68rem] font-semibold text-[var(--text-tertiary)]">{label}</div><div className="mt-1 truncate text-xs font-bold text-[var(--text-primary)]">{value}</div></div>;
}
