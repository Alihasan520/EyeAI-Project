import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  BookOpenCheck,
  CalendarDays,
  CheckCircle2,
  ChevronDown,
  Download,
  FileCheck2,
  FileText,
  LoaderCircle,
  Printer,
  ScanLine,
  ShieldCheck,
  Sparkles,
  UserRound,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { useSearchParams } from "react-router-dom";

import { ReferenceModal } from "../components/assistant/ReferenceModal";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { Modal } from "../components/ui/Modal";
import { PageHeader } from "../components/ui/PageHeader";
import { useAuthStore } from "../features/auth/auth-store";
import {
  createReport,
  downloadAuthenticatedFile,
  fetchAuthenticatedFile,
  generateReportDraft,
  getTimeline,
  listPatients,
  listReports,
  listVisits,
} from "../lib/api";
import { formatDate } from "../lib/format";
import { useI18n } from "../lib/i18n";
import type {
  AssistantReference,
  AssistantResult,
  ReportListItem,
  ReportRecord,
  StoredPrediction,
  VisitListItem,
} from "../lib/types";

export function ReportsPage() {
  const { t } = useI18n();
  const previewMode = useAuthStore((state) => state.previewMode);
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const [patientRef, setPatientRef] = useState(searchParams.get("patient") || "");
  const [visitRef, setVisitRef] = useState(searchParams.get("visit") || "");
  const [draft, setDraft] = useState<AssistantResult | null>(null);
  const [generatedReport, setGeneratedReport] = useState<ReportRecord | null>(null);
  const [selectedReference, setSelectedReference] = useState<AssistantReference | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  const patientsQuery = useQuery({
    queryKey: ["patients", "reports"],
    queryFn: () => listPatients(),
    enabled: !previewMode,
  });
  const visitsQuery = useQuery({
    queryKey: ["visits", "reports"],
    queryFn: () => listVisits(),
    enabled: !previewMode,
  });
  const reportsQuery = useQuery({
    queryKey: ["reports", patientRef],
    queryFn: () => listReports(patientRef || undefined),
    enabled: !previewMode,
  });

  const patients = patientsQuery.data || [];
  const visits = visitsQuery.data || [];
  const selectedVisit = visits.find((item) => item.visit.display_id === visitRef);
  const patientVisits = useMemo(
    () => visits.filter((item) => !patientRef || item.patient_display_id === patientRef),
    [patientRef, visits],
  );

  const timelineQuery = useQuery({
    queryKey: ["timeline", "report", selectedVisit?.patient_display_id, selectedVisit?.visit.eye],
    queryFn: () => getTimeline(selectedVisit!.patient_display_id, selectedVisit!.visit.eye),
    enabled: !previewMode && Boolean(selectedVisit),
  });
  const selectedEntry = timelineQuery.data?.find((entry) => entry.visit.display_id === visitRef);
  const prediction = selectedEntry?.prediction || null;

  useEffect(() => {
    if (!visitRef) return;
    const visit = visits.find((item) => item.visit.display_id === visitRef);
    if (visit) setPatientRef(visit.patient_display_id);
  }, [visitRef, visits]);

  useEffect(() => {
    const params: Record<string, string> = {};
    if (patientRef) params.patient = patientRef;
    if (visitRef) params.visit = visitRef;
    setSearchParams(params, { replace: true });
  }, [patientRef, setSearchParams, visitRef]);

  useEffect(() => () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
  }, [previewUrl]);

  const draftMutation = useMutation({
    mutationFn: () => {
      if (!visitRef) throw new Error(t("selectVisitForReport"));
      return generateReportDraft(visitRef);
    },
    onSuccess: (payload) => setDraft(payload.result),
  });

  const reportMutation = useMutation({
    mutationFn: () => {
      if (!visitRef) throw new Error(t("selectVisitForReport"));
      return createReport(visitRef, {
        clinical_summary: draft?.answer || null,
        references: (draft?.references || []) as Record<string, unknown>[],
      });
    },
    onSuccess: (report) => {
      setGeneratedReport(report);
      void queryClient.invalidateQueries({ queryKey: ["reports"] });
    },
  });

  const openPreview = async (report: ReportRecord) => {
    const blob = await fetchAuthenticatedFile(report.download_url);
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(URL.createObjectURL(blob));
  };

  const downloadReport = (report: ReportRecord) =>
    downloadAuthenticatedFile(report.download_url, `${report.display_id}-eyeai-report.pdf`);

  const requestError = draftMutation.error || reportMutation.error;

  if (previewMode) {
    return (
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
        <PageHeader eyebrow="EyeAI Clinical Intelligence" title={t("reports")} description={t("reportsDescription")} />
        <EmptyState icon={<FileText size={26} />} title={t("liveBackendRequired")} description={t("reportsPreviewDisabled")} />
      </motion.div>
    );
  }

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
      <PageHeader
        eyebrow="EyeAI Clinical Intelligence"
        title={t("clinicalReports")}
        description={t("reportsDescription")}
        actions={<Badge tone="primary" dot>{t("englishPdfOutput")}</Badge>}
      />

      <div className="grid gap-6 xl:grid-cols-[minmax(310px,0.78fr)_minmax(0,1.45fr)]">
        <div className="space-y-5">
          <Card className="overflow-hidden">
            <div className="border-b border-[var(--border)] bg-[linear-gradient(135deg,var(--primary-soft),var(--ai-soft))] p-5">
              <div className="flex items-center gap-3">
                <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[var(--surface)] text-[var(--primary)] shadow-sm">
                  <FileCheck2 size={21} />
                </span>
                <div>
                  <div className="font-extrabold text-[var(--text-primary)]">{t("buildClinicalReport")}</div>
                  <div className="text-xs text-[var(--text-secondary)]">{t("buildClinicalReportHint")}</div>
                </div>
              </div>
            </div>
            <div className="space-y-4 p-5">
              <SelectBlock label={t("patient")} icon={<UserRound size={16} />}>
                <select
                  className="analysis-select"
                  value={patientRef}
                  onChange={(event) => {
                    setPatientRef(event.target.value);
                    setVisitRef("");
                    setDraft(null);
                    setGeneratedReport(null);
                  }}
                >
                  <option value="">{t("allPatients")}</option>
                  {patients.map((patient) => (
                    <option key={patient.id} value={patient.display_id}>
                      {patient.first_name} {patient.last_name} · {patient.display_id}
                    </option>
                  ))}
                </select>
              </SelectBlock>

              <SelectBlock label={t("visit")} icon={<CalendarDays size={16} />}>
                <select
                  className="analysis-select"
                  value={visitRef}
                  onChange={(event) => {
                    setVisitRef(event.target.value);
                    setDraft(null);
                    setGeneratedReport(null);
                  }}
                >
                  <option value="">{t("selectVisitForReport")}</option>
                  {patientVisits.map((item) => (
                    <option key={item.visit.id} value={item.visit.display_id}>
                      {item.patient_name} · {item.visit.display_id} · {item.visit.eye === "right" ? t("rightEye") : t("leftEye")}
                    </option>
                  ))}
                </select>
              </SelectBlock>

              {selectedVisit ? <VisitSummary item={selectedVisit} prediction={prediction} /> : null}

              <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-1 2xl:grid-cols-2">
                <Button
                  variant="secondary"
                  icon={draftMutation.isPending ? <LoaderCircle size={17} className="animate-spin" /> : <Sparkles size={17} />}
                  disabled={!prediction || draftMutation.isPending}
                  onClick={() => draftMutation.mutate()}
                >
                  {t("prepareAiDraft")}
                </Button>
                <Button
                  icon={reportMutation.isPending ? <LoaderCircle size={17} className="animate-spin" /> : <FileText size={17} />}
                  disabled={!prediction || reportMutation.isPending}
                  onClick={() => reportMutation.mutate()}
                >
                  {t("generatePdf")}
                </Button>
              </div>

              {!prediction && visitRef && !timelineQuery.isLoading ? (
                <div className="rounded-2xl bg-[var(--warning-soft)] px-4 py-3 text-xs font-semibold leading-5 text-[var(--warning)]">
                  {t("reportRequiresAnalysis")}
                </div>
              ) : null}

              {requestError ? (
                <div className="rounded-2xl bg-[var(--danger-soft)] px-4 py-3 text-xs font-semibold text-[var(--danger)]">
                  {requestError instanceof Error ? requestError.message : t("requestFailed")}
                </div>
              ) : null}
            </div>
          </Card>

          <Card className="p-5">
            <div className="flex items-center gap-2 font-extrabold text-[var(--text-primary)]">
              <ShieldCheck size={18} className="text-[var(--primary)]" />
              {t("reportContents")}
            </div>
            <div className="mt-4 space-y-3">
              {[t("patientAndVisitDetails"), t("screeningResultAndThreshold"), t("originalAndHeatmapImages"), t("heatmapSpatialMetrics"), t("doctorNotesAndReferences"), t("clinicalDisclaimer")].map((item) => (
                <div key={item} className="flex items-start gap-3 text-xs leading-5 text-[var(--text-secondary)]">
                  <CheckCircle2 size={15} className="mt-0.5 shrink-0 text-[var(--success)]" /> {item}
                </div>
              ))}
            </div>
          </Card>
        </div>

        <div className="space-y-5">
          {draft ? <ReportDraftCard draft={draft} onReference={setSelectedReference} /> : (
            <Card className="flex min-h-[360px] items-center justify-center p-8">
              <EmptyState
                icon={<FileText size={27} />}
                title={t("reportPreviewReadyTitle")}
                description={t("reportPreviewReadyDescription")}
              />
            </Card>
          )}

          {generatedReport ? (
            <Card className="border-[var(--success)]/35 bg-[var(--success-soft)] p-5">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex items-center gap-3">
                  <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[var(--surface)] text-[var(--success)] shadow-sm">
                    <FileCheck2 size={21} />
                  </span>
                  <div>
                    <div className="font-extrabold text-[var(--text-primary)]">{t("reportGenerated")}</div>
                    <div className="mt-1 text-xs text-[var(--text-secondary)]">{generatedReport.display_id}</div>
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button variant="secondary" size="sm" icon={<ScanLine size={16} />} onClick={() => void openPreview(generatedReport)}>{t("previewReport")}</Button>
                  <Button size="sm" icon={<Download size={16} />} onClick={() => void downloadReport(generatedReport)}>{t("downloadPdf")}</Button>
                </div>
              </div>
            </Card>
          ) : null}

          <ReportsRegistry
            reports={reportsQuery.data || []}
            onPreview={(report) => void openPreview(report)}
            onDownload={(report) => void downloadReport(report)}
          />
        </div>
      </div>

      <ReferenceModal reference={selectedReference} onClose={() => setSelectedReference(null)} />
      <Modal
        open={Boolean(previewUrl)}
        onClose={() => {
          if (previewUrl) URL.revokeObjectURL(previewUrl);
          setPreviewUrl(null);
        }}
        title={t("pdfReportPreview")}
        description={t("pdfReportPreviewDescription")}
        maxWidth="max-w-6xl"
      >
        {previewUrl ? (
          <div className="h-[72vh] overflow-hidden rounded-2xl border border-[var(--border)] bg-white">
            <iframe title={t("pdfReportPreview")} src={previewUrl} className="h-full w-full" />
          </div>
        ) : null}
      </Modal>
    </motion.div>
  );
}

function VisitSummary({ item, prediction }: { item: VisitListItem; prediction: StoredPrediction | null }) {
  const { t, language } = useI18n();
  return (
    <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface-muted)] p-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="neutral">{item.patient_display_id}</Badge>
        <Badge tone="primary">{item.visit.eye === "right" ? t("rightEye") : t("leftEye")}</Badge>
        {prediction ? <Badge tone={prediction.quality_status === "review_required" ? "warning" : "success"}>{prediction.label}</Badge> : <Badge tone="neutral">{t("notAnalyzed")}</Badge>}
      </div>
      <div className="mt-3 font-extrabold text-[var(--text-primary)]">{item.patient_name}</div>
      <div className="mt-1 flex items-center gap-2 text-xs text-[var(--text-tertiary)]">
        <CalendarDays size={14} /> {formatDate(item.visit.visit_date, language)} · {item.visit.display_id}
      </div>
      {prediction ? (
        <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
          <Metric label={t("modelScore")} value={prediction.probability.toFixed(4)} />
          <Metric label={t("thresholdShort")} value={prediction.threshold.toFixed(3)} />
        </div>
      ) : null}
    </div>
  );
}

function ReportDraftCard({ draft, onReference }: { draft: AssistantResult; onReference: (reference: AssistantReference) => void }) {
  const { t } = useI18n();
  const references = (draft.references || []) as AssistantReference[];
  return (
    <Card className="overflow-hidden">
      <div className="border-b border-[var(--border)] bg-[linear-gradient(135deg,var(--primary-soft),var(--ai-soft))] p-5">
        <div className="flex items-center gap-3">
          <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[var(--surface)] text-[var(--ai-accent)] shadow-sm">
            <Sparkles size={21} />
          </span>
          <div>
            <div className="font-extrabold text-[var(--text-primary)]">{t("aiReportDraft")}</div>
            <div className="text-xs text-[var(--text-secondary)]">{t("aiReportDraftHint")}</div>
          </div>
        </div>
      </div>
      <div className="space-y-5 p-5">
        <section>
          <div className="mb-2 text-xs font-extrabold uppercase tracking-[0.12em] text-[var(--text-tertiary)]">{t("clinicalSummary")}</div>
          <p className="whitespace-pre-wrap text-sm leading-7 text-[var(--text-primary)]">{draft.answer || t("noDraftContent")}</p>
        </section>
        {draft.suggested_review ? (
          <section className="rounded-2xl bg-[var(--success-soft)] p-4">
            <div className="text-xs font-extrabold text-[var(--success)]">{t("suggestedReview")}</div>
            <p className="mt-2 text-xs leading-6 text-[var(--text-secondary)]">{draft.suggested_review}</p>
          </section>
        ) : null}
        {references.length ? (
          <section>
            <div className="mb-3 flex items-center gap-2 text-xs font-extrabold text-[var(--text-primary)]"><BookOpenCheck size={16} className="text-[var(--primary)]" />{t("sources")}</div>
            <div className="grid gap-2 sm:grid-cols-2">
              {references.map((reference, index) => (
                <button key={`${reference.source_id || index}-${reference.page || index}`} type="button" onClick={() => onReference(reference)} className="rounded-xl border border-[var(--border)] p-3 text-start transition-all hover:border-[var(--primary)] hover:bg-[var(--surface-hover)]">
                  <div className="text-xs font-bold text-[var(--text-primary)]">[{reference.citation_number || index + 1}] {reference.source_id || t("source")}</div>
                  <div className="mt-1 text-[0.65rem] text-[var(--text-tertiary)]">{reference.section || t("clinicalSection")} · {t("page")} {reference.page ?? "—"}</div>
                </button>
              ))}
            </div>
          </section>
        ) : null}
      </div>
    </Card>
  );
}

function ReportsRegistry({ reports, onPreview, onDownload }: { reports: ReportListItem[]; onPreview: (report: ReportRecord) => void; onDownload: (report: ReportRecord) => void }) {
  const { t, language } = useI18n();
  return (
    <Card className="overflow-hidden">
      <div className="flex items-center justify-between gap-3 border-b border-[var(--border)] px-5 py-4">
        <div>
          <div className="font-extrabold text-[var(--text-primary)]">{t("reportRegistry")}</div>
          <div className="mt-1 text-xs text-[var(--text-secondary)]">{t("reportRegistryHint")}</div>
        </div>
        <Badge tone="neutral">{reports.length}</Badge>
      </div>
      {reports.length ? (
        <div className="divide-y divide-[var(--border)]">
          {reports.map((item) => (
            <div key={item.report.id} className="flex flex-col gap-4 p-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex min-w-0 items-center gap-3">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[var(--primary-soft)] text-[var(--primary)]"><FileText size={18} /></span>
                <div className="min-w-0">
                  <div className="truncate text-sm font-extrabold text-[var(--text-primary)]">{item.patient_name} · {item.report.display_id}</div>
                  <div className="mt-1 flex flex-wrap items-center gap-2 text-[0.68rem] text-[var(--text-tertiary)]">
                    <span>{item.patient_display_id}</span><span>·</span><span>{item.eye === "right" ? t("rightEye") : t("leftEye")}</span><span>·</span><span>{formatDate(item.report.created_at, language)}</span>
                  </div>
                </div>
              </div>
              <div className="flex gap-2">
                <Button variant="ghost" size="sm" icon={<Printer size={15} />} onClick={() => onPreview(item.report)}>{t("preview")}</Button>
                <Button variant="secondary" size="sm" icon={<Download size={15} />} onClick={() => onDownload(item.report)}>{t("download")}</Button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="p-7 text-center text-xs text-[var(--text-tertiary)]">{t("noReportsYet")}</div>
      )}
    </Card>
  );
}

function SelectBlock({ label, icon, children }: { label: string; icon: ReactNode; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-2 flex items-center gap-2 text-sm font-semibold text-[var(--text-primary)]">{icon}{label}</span>
      <span className="relative block">{children}<ChevronDown size={16} className="pointer-events-none absolute end-4 top-1/2 -translate-y-1/2 text-[var(--text-tertiary)]" /></span>
    </label>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="rounded-xl bg-[var(--surface)] p-3"><div className="text-[0.65rem] text-[var(--text-tertiary)]">{label}</div><div className="mt-1 font-mono font-extrabold tabular-nums text-[var(--text-primary)]">{value}</div></div>;
}
