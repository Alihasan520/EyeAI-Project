import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import {
  AlertTriangle,
  ArrowRight,
  Check,
  ChevronDown,
  Eye,
  FileImage,
  Focus,
  Image as ImageIcon,
  Info,
  LoaderCircle,
  Maximize2,
  Microscope,
  ScanLine,
  ShieldCheck,
  Sparkles,
  UploadCloud,
  WandSparkles,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { ImageReviewModal } from "../components/analysis/ImageReviewModal";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { PageHeader } from "../components/ui/PageHeader";
import { SegmentedControl } from "../components/ui/SegmentedControl";
import { useAuthStore } from "../features/auth/auth-store";
import {
  analyzeVisit,
  buildArtifactUrl,
  createVisit,
  getTimeline,
  listPatients,
  listVisits,
} from "../lib/api";
import { formatDate } from "../lib/format";
import { useI18n } from "../lib/i18n";
import type {
  ExplanationArtifact,
  EyeSide,
  Patient,
  StoredPrediction,
  VisitListItem,
} from "../lib/types";

const NEW_VISIT = "__new_visit__";
const ACCEPTED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp"];
const MAX_UPLOAD_BYTES = 25 * 1024 * 1024;

export function AnalysisPage() {
  const { t, language } = useI18n();
  const navigate = useNavigate();
  const previewMode = useAuthStore((state) => state.previewMode);
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const stageTimerRef = useRef<number | null>(null);

  const [patientRef, setPatientRef] = useState(searchParams.get("patient") || "");
  const [eye, setEye] = useState<EyeSide>("right");
  const [visitChoice, setVisitChoice] = useState(searchParams.get("visit") || NEW_VISIT);
  const [visitNotes, setVisitNotes] = useState("");
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [processingStage, setProcessingStage] = useState<number | null>(null);
  const [result, setResult] = useState<StoredPrediction | null>(null);
  const [viewer, setViewer] = useState<{ url: string; title: string; key: string } | null>(null);

  const patientsQuery = useQuery({
    queryKey: ["patients", "analysis"],
    queryFn: () => listPatients(),
    enabled: !previewMode,
  });
  const visitsQuery = useQuery({
    queryKey: ["visits", "analysis"],
    queryFn: () => listVisits(),
    enabled: !previewMode,
  });

  const patients = patientsQuery.data || [];
  const visits = visitsQuery.data || [];
  const selectedVisitItem = visits.find((item) => item.visit.display_id === visitChoice);
  const selectedPatient = patients.find((patient) => patient.display_id === patientRef);

  useEffect(() => {
    const visitFromUrl = searchParams.get("visit");
    if (!visitFromUrl || !visits.length) return;
    const item = visits.find((visitItem) => visitItem.visit.display_id === visitFromUrl);
    if (!item) return;
    setVisitChoice(item.visit.display_id);
    setPatientRef(item.patient_display_id);
    setEye(item.visit.eye);
  }, [searchParams, visits]);

  const patientVisits = useMemo(
    () => visits.filter((item) => item.patient_display_id === patientRef && item.visit.eye === eye),
    [eye, patientRef, visits],
  );

  const timelineQuery = useQuery({
    queryKey: ["timeline", selectedVisitItem?.patient_display_id, selectedVisitItem?.visit.eye],
    queryFn: () =>
      getTimeline(selectedVisitItem!.patient_display_id, selectedVisitItem!.visit.eye),
    enabled: !previewMode && Boolean(selectedVisitItem),
  });

  useEffect(() => {
    if (!selectedVisitItem || !timelineQuery.data) return;
    const timelineEntry = timelineQuery.data.find(
      (entry) => entry.visit.display_id === selectedVisitItem.visit.display_id,
    );
    if (timelineEntry?.prediction) setResult(timelineEntry.prediction);
    else setResult(null);
  }, [selectedVisitItem, timelineQuery.data]);

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
      if (stageTimerRef.current) window.clearInterval(stageTimerRef.current);
    };
  }, [previewUrl]);

  const analysisMutation = useMutation({
    mutationFn: async () => {
      if (!imageFile) throw new Error(t("selectFundusImageFirst"));
      let targetVisitRef = visitChoice;
      if (visitChoice === NEW_VISIT) {
        if (!patientRef) throw new Error(t("selectPatientFirst"));
        const newVisit = await createVisit(patientRef, {
          eye,
          notes: visitNotes.trim() || null,
        });
        targetVisitRef = newVisit.display_id;
      }
      const prediction = await analyzeVisit(targetVisitRef, imageFile, true);
      return { prediction, targetVisitRef };
    },
    onMutate: () => {
      setProcessingStage(0);
      if (stageTimerRef.current) window.clearInterval(stageTimerRef.current);
      stageTimerRef.current = window.setInterval(() => {
        setProcessingStage((current) => {
          if (current == null) return 0;
          return Math.min(current + 1, 4);
        });
      }, 1700);
    },
    onSuccess: ({ prediction, targetVisitRef }) => {
      if (stageTimerRef.current) window.clearInterval(stageTimerRef.current);
      setProcessingStage(5);
      setResult(prediction);
      setVisitChoice(targetVisitRef);
      setSearchParams({ visit: targetVisitRef });
      void queryClient.invalidateQueries({ queryKey: ["visits"] });
      void queryClient.invalidateQueries({ queryKey: ["timeline"] });
      window.setTimeout(() => setProcessingStage(null), 900);
    },
    onError: () => {
      if (stageTimerRef.current) window.clearInterval(stageTimerRef.current);
      setProcessingStage(null);
    },
  });

  const chooseImage = (file: File | null) => {
    setFileError(null);
    if (!file) return;
    if (!ACCEPTED_IMAGE_TYPES.includes(file.type)) {
      setFileError(t("unsupportedImageType"));
      return;
    }
    if (file.size > MAX_UPLOAD_BYTES) {
      setFileError(t("imageTooLarge"));
      return;
    }
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setImageFile(file);
    setPreviewUrl(URL.createObjectURL(file));
    setResult(null);
  };

  const resetUpload = () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(null);
    setImageFile(null);
    setFileError(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const originalArtifact = result?.explanation?.artifacts?.original;
  const overlayArtifact = result?.explanation?.artifacts?.overlay;
  const originalUrl = artifactUrl(originalArtifact) || previewUrl;
  const overlayUrl = artifactUrl(overlayArtifact);
  const metrics = result?.explanation?.metrics || {};
  const qualityWarnings = readStringArray(result?.quality?.warnings);
  const ttaDisagreement = readNumber(result?.tta?.absolute_disagreement);

  const openViewer = (url: string, title: string, suffix: string) => {
    setViewer({
      url,
      title,
      key: `${result?.display_id || "pending"}-${suffix}`,
    });
  };

  if (previewMode) {
    return (
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
        <PageHeader
          eyebrow="EyeAI Clinical Intelligence"
          title={t("analysisWorkspace")}
          description={t("analysisWorkspaceDescription")}
        />
        <EmptyState
          icon={<Microscope size={26} />}
          title={t("liveBackendRequired")}
          description={t("analysisPreviewDisabled")}
        />
      </motion.div>
    );
  }

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
      <PageHeader
        eyebrow="EyeAI Clinical Intelligence"
        title={t("analysisWorkspace")}
        description={t("analysisWorkspaceDescription")}
        actions={
          result ? (
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={result.quality_status === "review_required" ? "warning" : "success"} dot>
                {result.quality_status === "review_required" ? t("reviewRequired") : t("analysisComplete")}
              </Badge>
              {visitChoice !== NEW_VISIT ? (
                <>
                  <Button
                    size="sm"
                    variant="secondary"
                    icon={<Sparkles size={15} />}
                    onClick={() => navigate(`/assistant?patient=${encodeURIComponent(patientRef)}&visit=${encodeURIComponent(visitChoice)}&eye=${eye}`)}
                  >
                    {t("askClinicalCopilot")}
                  </Button>
                  <Button
                    size="sm"
                    variant="secondary"
                    icon={<FileImage size={15} />}
                    onClick={() => navigate(`/reports?patient=${encodeURIComponent(patientRef)}&visit=${encodeURIComponent(visitChoice)}`)}
                  >
                    {t("createClinicalReport")}
                  </Button>
                </>
              ) : null}
            </div>
          ) : undefined
        }
      />

      <div className="grid gap-6 xl:grid-cols-[minmax(310px,0.72fr)_minmax(0,1.55fr)]">
        <div className="space-y-5">
          <Card className="overflow-hidden">
            <div className="border-b border-[var(--border)] bg-[linear-gradient(135deg,var(--primary-soft),var(--ai-soft))] px-5 py-4">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-[var(--surface)] text-[var(--primary)] shadow-sm">
                  <WandSparkles size={19} />
                </div>
                <div>
                  <h3 className="font-extrabold text-[var(--text-primary)]">{t("newRetinalAnalysis")}</h3>
                  <p className="mt-0.5 text-xs text-[var(--text-secondary)]">{t("newRetinalAnalysisHint")}</p>
                </div>
              </div>
            </div>

            <div className="space-y-5 p-5">
              <SelectBlock label={t("patient")} icon={<Eye size={16} />}>
                <select
                  value={patientRef}
                  onChange={(event) => {
                    setPatientRef(event.target.value);
                    setVisitChoice(NEW_VISIT);
                    setResult(null);
                  }}
                  className="analysis-select"
                >
                  <option value="">{t("selectPatient")}</option>
                  {patients.map((patient) => (
                    <option key={patient.id} value={patient.display_id}>
                      {patient.first_name} {patient.last_name} — {patient.display_id}
                    </option>
                  ))}
                </select>
              </SelectBlock>

              <div>
                <div className="mb-2 text-sm font-semibold text-[var(--text-primary)]">{t("selectedEye")}</div>
                <SegmentedControl
                  value={eye}
                  options={[
                    { value: "right", label: t("rightEye") },
                    { value: "left", label: t("leftEye") },
                  ]}
                  onChange={(value) => {
                    setEye(value);
                    setVisitChoice(NEW_VISIT);
                    setResult(null);
                  }}
                />
              </div>

              <SelectBlock label={t("visit")} icon={<ScanLine size={16} />}>
                <select
                  value={visitChoice}
                  onChange={(event) => {
                    const value = event.target.value;
                    setVisitChoice(value);
                    setResult(null);
                    if (value !== NEW_VISIT) setSearchParams({ visit: value });
                  }}
                  className="analysis-select"
                  disabled={!patientRef}
                >
                  <option value={NEW_VISIT}>{t("createNewVisitForAnalysis")}</option>
                  {patientVisits.map((item) => (
                    <option key={item.visit.id} value={item.visit.display_id}>
                      {item.visit.display_id} — {formatDate(item.visit.visit_date, language)}
                    </option>
                  ))}
                </select>
              </SelectBlock>

              {visitChoice === NEW_VISIT ? (
                <label className="block">
                  <span className="mb-2 block text-sm font-semibold text-[var(--text-primary)]">{t("visitNotes")}</span>
                  <textarea
                    value={visitNotes}
                    onChange={(event) => setVisitNotes(event.target.value)}
                    placeholder={t("visitNotesPlaceholder")}
                    className="min-h-24 w-full resize-y rounded-xl border border-[var(--border)] bg-[var(--surface-muted)] px-4 py-3 text-sm text-[var(--text-primary)] outline-none transition-all placeholder:text-[var(--text-tertiary)] focus:border-[var(--primary)] focus:ring-4 focus:ring-[var(--primary-soft)]"
                  />
                </label>
              ) : null}

              <div>
                <div className="mb-2 flex items-center justify-between gap-3">
                  <span className="text-sm font-semibold text-[var(--text-primary)]">{t("fundusImage")}</span>
                  {imageFile ? (
                    <button type="button" onClick={resetUpload} className="text-xs font-bold text-[var(--danger)] hover:underline">
                      {t("removeImage")}
                    </button>
                  ) : null}
                </div>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  className="hidden"
                  onChange={(event) => chooseImage(event.target.files?.[0] || null)}
                />
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  onDragEnter={(event) => { event.preventDefault(); setDragActive(true); }}
                  onDragOver={(event) => { event.preventDefault(); setDragActive(true); }}
                  onDragLeave={(event) => { event.preventDefault(); setDragActive(false); }}
                  onDrop={(event) => {
                    event.preventDefault();
                    setDragActive(false);
                    chooseImage(event.dataTransfer.files?.[0] || null);
                  }}
                  className={`relative flex min-h-52 w-full flex-col items-center justify-center overflow-hidden rounded-2xl border-2 border-dashed px-5 py-6 text-center transition-all ${
                    dragActive
                      ? "border-[var(--primary)] bg-[var(--primary-soft)]"
                      : "border-[var(--border)] bg-[var(--surface-muted)] hover:border-[var(--primary)]/55 hover:bg-[var(--surface-hover)]"
                  }`}
                >
                  {previewUrl ? (
                    <>
                      <img src={previewUrl} alt={t("selectedFundusPreview")} className="absolute inset-0 h-full w-full object-contain opacity-78" />
                      <span className="absolute inset-0 bg-[linear-gradient(180deg,transparent_30%,rgba(2,7,17,.78))]" />
                      <span className="relative mt-auto max-w-full truncate rounded-full bg-black/45 px-3 py-1.5 text-xs font-bold text-white backdrop-blur-md">
                        {imageFile?.name}
                      </span>
                    </>
                  ) : (
                    <>
                      <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-[linear-gradient(135deg,var(--primary-soft),var(--ai-soft))] text-[var(--primary)]">
                        <UploadCloud size={26} />
                      </span>
                      <span className="mt-4 text-sm font-extrabold text-[var(--text-primary)]">{t("dropFundusImage")}</span>
                      <span className="mt-1.5 text-xs leading-5 text-[var(--text-tertiary)]">{t("supportedImageHint")}</span>
                    </>
                  )}
                </button>
                {fileError ? <div className="mt-2 text-xs font-semibold text-[var(--danger)]">{fileError}</div> : null}
              </div>

              <Button
                fullWidth
                size="lg"
                icon={analysisMutation.isPending ? <LoaderCircle size={19} className="animate-spin" /> : <Microscope size={19} />}
                disabled={!patientRef || !imageFile || analysisMutation.isPending}
                onClick={() => analysisMutation.mutate()}
              >
                {analysisMutation.isPending ? t("analysisInProgress") : t("runAnalysis")}
              </Button>

              {analysisMutation.error ? (
                <div className="rounded-xl bg-[var(--danger-soft)] px-4 py-3 text-sm font-semibold text-[var(--danger)]">
                  {analysisMutation.error instanceof Error ? analysisMutation.error.message : t("requestFailed")}
                </div>
              ) : null}
            </div>
          </Card>

          <AnimatePresence>
            {processingStage != null ? <ProcessingCard stage={processingStage} /> : null}
          </AnimatePresence>
        </div>

        <div className="min-w-0">
          {result ? (
            <AnalysisResult
              result={result}
              originalUrl={originalUrl}
              overlayUrl={overlayUrl}
              metrics={metrics}
              qualityWarnings={qualityWarnings}
              ttaDisagreement={ttaDisagreement}
              selectedPatient={selectedPatient}
              selectedVisitItem={selectedVisitItem}
              onOpenViewer={openViewer}
            />
          ) : (
            <Card className="flex min-h-[690px] items-center justify-center overflow-hidden p-8">
              <div className="relative max-w-lg text-center">
                <div className="pointer-events-none absolute -inset-24 -z-10 rounded-full bg-[radial-gradient(circle,var(--primary-soft),transparent_68%)]" />
                <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-[1.65rem] bg-[linear-gradient(135deg,var(--primary-soft),var(--ai-soft))] text-[var(--primary)] shadow-[0_20px_50px_-30px_var(--primary)]">
                  <Microscope size={35} strokeWidth={1.65} />
                </div>
                <h3 className="mt-6 text-2xl font-extrabold tracking-[-0.03em] text-[var(--text-primary)]">{t("analysisReadyTitle")}</h3>
                <p className="mt-3 text-sm leading-7 text-[var(--text-secondary)]">{t("analysisReadyDescription")}</p>
                <div className="mt-7 grid gap-3 sm:grid-cols-3">
                  <Feature icon={<FileImage size={18} />} label={t("secureImageUpload")} />
                  <Feature icon={<Sparkles size={18} />} label={t("ttaExplainability")} />
                  <Feature icon={<ShieldCheck size={18} />} label={t("clinicalReviewOutput")} />
                </div>
              </div>
            </Card>
          )}
        </div>
      </div>

      {viewer ? (
        <ImageReviewModal
          open
          onClose={() => setViewer(null)}
          imageUrl={viewer.url}
          title={viewer.title}
          subtitle={t("imageViewerSubtitle")}
          annotationKey={viewer.key}
        />
      ) : null}
    </motion.div>
  );
}

function AnalysisResult({
  result,
  originalUrl,
  overlayUrl,
  metrics,
  qualityWarnings,
  ttaDisagreement,
  selectedPatient,
  selectedVisitItem,
  onOpenViewer,
}: {
  result: StoredPrediction;
  originalUrl: string | null;
  overlayUrl: string | null;
  metrics: Record<string, unknown>;
  qualityWarnings: string[];
  ttaDisagreement: number | null;
  selectedPatient?: Patient;
  selectedVisitItem?: VisitListItem;
  onOpenViewer: (url: string, title: string, suffix: string) => void;
}) {
  const { t } = useI18n();
  const peakX = readNumber(metrics.peak_x_pixel);
  const peakY = readNumber(metrics.peak_y_pixel);
  const peakXFraction = readNumber(metrics.peak_x_fraction);
  const peakYFraction = readNumber(metrics.peak_y_fraction);
  const dominantRegion = readString(metrics.dominant_region);
  const mapSimilarity = readNumber(metrics.tta_map_similarity);
  const fundusFocus = readNumber(metrics.fundus_focus_fraction);
  const borderFocus = readNumber(metrics.border_focus_fraction);
  const distanceFromThreshold = result.probability - result.threshold;

  return (
    <div className="space-y-5">
      <Card className="overflow-hidden">
        <div className="flex flex-col gap-5 border-b border-[var(--border)] bg-[linear-gradient(135deg,var(--primary-soft),var(--ai-soft))] p-5 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="ai" dot>{t("analysisComplete")}</Badge>
              <Badge tone={result.decision ? "danger" : "success"}>{result.label}</Badge>
              <Badge tone={result.quality_status === "review_required" ? "warning" : "success"}>{humanize(result.quality_status)}</Badge>
            </div>
            <h3 className="mt-4 text-2xl font-extrabold tracking-[-0.035em] text-[var(--text-primary)]">{t("amdScreeningOutput")}</h3>
            <p className="mt-2 text-sm text-[var(--text-secondary)]">
              {[selectedPatient ? `${selectedPatient.first_name} ${selectedPatient.last_name}` : null, selectedVisitItem?.visit.display_id, result.display_id]
                .filter(Boolean)
                .join(" · ")}
            </p>
          </div>
          <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] px-5 py-4 text-center shadow-sm">
            <div className="text-[0.68rem] font-extrabold uppercase tracking-[0.16em] text-[var(--text-tertiary)]">{t("modelScore")}</div>
            <div className="mt-1 font-mono text-3xl font-black tabular-nums text-[var(--text-primary)]">{result.probability.toFixed(4)}</div>
            <div className="mt-1 text-xs text-[var(--text-tertiary)]">{t("thresholdShort")} {result.threshold.toFixed(3)}</div>
          </div>
        </div>

        <div className="p-5">
          <ScoreScale score={result.probability} threshold={result.threshold} />
          <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <ResultMetric label={t("scoreAboveThreshold")} value={`${distanceFromThreshold >= 0 ? "+" : ""}${distanceFromThreshold.toFixed(4)}`} icon={<ArrowRight size={17} />} />
            <ResultMetric label={t("imageQuality")} value={humanize(result.quality_status)} icon={<ShieldCheck size={17} />} />
            <ResultMetric label={t("ttaDisagreement")} value={ttaDisagreement == null ? "—" : ttaDisagreement.toFixed(4)} icon={<Sparkles size={17} />} />
            <ResultMetric label={t("modelVersion")} value={result.model_version} icon={<Info size={17} />} />
          </div>
        </div>
      </Card>

      <div className="grid gap-5 lg:grid-cols-2">
        <ClinicalImageCard
          title={t("originalFundusImage")}
          description={t("originalFundusDescription")}
          url={originalUrl}
          badge={t("original")}
          onOpen={() => originalUrl && onOpenViewer(originalUrl, t("originalFundusImage"), "original")}
        />
        <ClinicalImageCard
          title={t("heatmapOverlayImage")}
          description={t("heatmapOverlayDescription")}
          url={overlayUrl}
          badge={t("modelInfluence")}
          accent
          onOpen={() => overlayUrl && onOpenViewer(overlayUrl, t("heatmapOverlayImage"), "overlay")}
        />
      </div>

      <div className="grid gap-5 xl:grid-cols-[1.15fr_0.85fr]">
        <Card className="p-5">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 font-extrabold text-[var(--text-primary)]"><Focus size={19} className="text-[var(--primary)]" />{t("heatmapSpatialReview")}</div>
              <p className="mt-1 text-xs leading-5 text-[var(--text-secondary)]">{t("heatmapSpatialReviewHint")}</p>
            </div>
            <Badge tone="ai">{humanize(dominantRegion || "not_available")}</Badge>
          </div>
          <div className="mt-5 grid gap-3 sm:grid-cols-2">
            <ResultMetric label={t("peakCoordinate")} value={peakX == null || peakY == null ? "—" : `(${Math.round(peakX)}, ${Math.round(peakY)})`} icon={<ScanLine size={17} />} />
            <ResultMetric label={t("normalizedCoordinate")} value={peakXFraction == null || peakYFraction == null ? "—" : `(${(peakXFraction * 100).toFixed(1)}%, ${(peakYFraction * 100).toFixed(1)}%)`} icon={<Focus size={17} />} />
            <ResultMetric label={t("ttaHeatmapSimilarity")} value={mapSimilarity == null ? "—" : mapSimilarity.toFixed(4)} icon={<Sparkles size={17} />} />
            <ResultMetric label={t("fundusFocusFraction")} value={fundusFocus == null ? "—" : `${(fundusFocus * 100).toFixed(1)}%`} icon={<Eye size={17} />} />
            <ResultMetric label={t("borderFocusFraction")} value={borderFocus == null ? "—" : `${(borderFocus * 100).toFixed(1)}%`} icon={<Maximize2 size={17} />} />
            <ResultMetric label={t("targetLabel")} value={result.explanation?.target_label || result.label} icon={<Microscope size={17} />} />
          </div>
          <div className="mt-4 rounded-2xl bg-[var(--ai-soft)] px-4 py-3 text-xs leading-6 text-[var(--text-secondary)]">
            <strong className="text-[var(--ai-accent)]">{t("important")}: </strong>
            {result.explanation?.disclaimer || t("heatmapDisclaimer")}
          </div>
        </Card>

        <Card className="p-5">
          <div className="flex items-center gap-2 font-extrabold text-[var(--text-primary)]">
            <AlertTriangle size={19} className={qualityWarnings.length ? "text-[var(--warning)]" : "text-[var(--success)]"} />
            {t("technicalReviewProfile")}
          </div>
          <div className="mt-4 space-y-3">
            <ReviewRow ok={result.probability >= result.threshold} text={result.probability >= result.threshold ? t("scoreExceedsThreshold") : t("scoreBelowThreshold")} />
            <ReviewRow ok={!qualityWarnings.length} text={qualityWarnings.length ? qualityWarnings.map(humanize).join(", ") : t("noImageQualityWarnings")} />
            <ReviewRow ok={mapSimilarity == null || mapSimilarity >= 0.15} text={mapSimilarity == null ? t("heatmapStabilityUnavailable") : `${t("heatmapSimilarityLabel")}: ${mapSimilarity.toFixed(4)}`} />
            <ReviewRow ok={fundusFocus == null || fundusFocus >= 0.7} text={fundusFocus == null ? t("fundusFocusUnavailable") : `${t("fundusFocusLabel")}: ${(fundusFocus * 100).toFixed(1)}%`} />
          </div>
          {result.explanation?.warnings?.length ? (
            <div className="mt-4 rounded-xl bg-[var(--warning-soft)] px-4 py-3 text-xs font-semibold leading-5 text-[var(--warning)]">
              {result.explanation.warnings.map(humanize).join(" · ")}
            </div>
          ) : null}
        </Card>
      </div>
    </div>
  );
}

function ProcessingCard({ stage }: { stage: number }) {
  const { t } = useI18n();
  const stages = [
    t("validatingImage"),
    t("checkingImageQuality"),
    t("runningRetfound"),
    t("aggregatingTta"),
    t("generatingHeatmap"),
    t("savingClinicalResult"),
  ];
  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, scale: 0.98 }}>
      <Card className="overflow-hidden p-5">
        <div className="flex items-center gap-3">
          <div className="relative flex h-11 w-11 items-center justify-center rounded-2xl bg-[linear-gradient(135deg,var(--primary-soft),var(--ai-soft))]">
            <span className="absolute inset-1 animate-spin rounded-xl border-2 border-transparent border-t-[var(--primary)] border-e-[var(--ai-accent)]" />
            <Sparkles size={17} className="text-[var(--primary)]" />
          </div>
          <div>
            <div className="font-extrabold text-[var(--text-primary)]">{t("analysisInProgress")}</div>
            <div className="mt-0.5 text-xs text-[var(--text-secondary)]">{stages[Math.min(stage, stages.length - 1)]}</div>
          </div>
        </div>
        <div className="mt-5 space-y-2.5">
          {stages.map((label, index) => {
            const done = index < stage;
            const current = index === stage;
            return (
              <div key={label} className={`flex items-center gap-3 rounded-xl px-3 py-2.5 transition-all ${current ? "bg-[var(--primary-soft)]" : ""}`}>
                <span className={`flex h-6 w-6 items-center justify-center rounded-full border text-xs ${done ? "border-[var(--success)] bg-[var(--success)] text-white" : current ? "border-[var(--primary)] text-[var(--primary)]" : "border-[var(--border)] text-[var(--text-tertiary)]"}`}>
                  {done ? <Check size={14} /> : current ? <LoaderCircle size={14} className="animate-spin" /> : index + 1}
                </span>
                <span className={`text-xs font-semibold ${current ? "text-[var(--primary)]" : done ? "text-[var(--text-primary)]" : "text-[var(--text-tertiary)]"}`}>{label}</span>
              </div>
            );
          })}
        </div>
      </Card>
    </motion.div>
  );
}

function ClinicalImageCard({
  title,
  description,
  url,
  badge,
  accent = false,
  onOpen,
}: {
  title: string;
  description: string;
  url: string | null;
  badge: string;
  accent?: boolean;
  onOpen: () => void;
}) {
  const { t } = useI18n();
  return (
    <Card className="group overflow-hidden">
      <button type="button" disabled={!url} onClick={onOpen} className="relative block aspect-[4/3] w-full overflow-hidden bg-[#030814] disabled:cursor-default">
        {url ? (
          <img src={url} alt={title} className="h-full w-full object-contain transition-transform duration-500 group-hover:scale-[1.025]" />
        ) : (
          <span className="flex h-full flex-col items-center justify-center gap-3 text-slate-500"><ImageIcon size={32} /><span className="text-xs font-semibold">{t("imageUnavailable")}</span></span>
        )}
        <span className={`absolute start-3 top-3 rounded-full px-3 py-1.5 text-xs font-bold backdrop-blur-md ${accent ? "bg-indigo-500/78 text-white" : "bg-black/55 text-white"}`}>{badge}</span>
        {url ? (
          <span className="absolute inset-0 flex items-center justify-center bg-black/0 opacity-0 transition-all duration-300 group-hover:bg-black/26 group-hover:opacity-100">
            <span className="inline-flex items-center gap-2 rounded-full bg-white/92 px-4 py-2 text-xs font-extrabold text-slate-900 shadow-xl"><Maximize2 size={16} />{t("openInteractiveViewer")}</span>
          </span>
        ) : null}
      </button>
      <div className="p-4">
        <div className="font-extrabold text-[var(--text-primary)]">{title}</div>
        <p className="mt-1 text-xs leading-5 text-[var(--text-secondary)]">{description}</p>
      </div>
    </Card>
  );
}

function ScoreScale({ score, threshold }: { score: number; threshold: number }) {
  const { t } = useI18n();
  const scorePosition = Math.max(0, Math.min(100, score * 100));
  const thresholdPosition = Math.max(0, Math.min(100, threshold * 100));
  return (
    <div>
      <div className="mb-2 flex items-center justify-between text-xs font-semibold text-[var(--text-tertiary)]">
        <span>0.000</span><span>{t("screeningScoreScale")}</span><span>1.000</span>
      </div>
      <div className="relative h-4 rounded-full bg-[linear-gradient(90deg,var(--success-soft),var(--warning-soft),var(--danger-soft))]">
        <span className="absolute top-1/2 h-7 w-0.5 -translate-y-1/2 bg-[var(--warning)]" style={{ left: `${thresholdPosition}%` }} />
        <motion.span initial={{ left: "0%" }} animate={{ left: `${scorePosition}%` }} transition={{ type: "spring", stiffness: 140, damping: 20 }} className="absolute top-1/2 h-5 w-5 -translate-x-1/2 -translate-y-1/2 rounded-full border-4 border-[var(--surface)] bg-[var(--danger)] shadow-lg" />
      </div>
      <div className="relative mt-2 h-5 text-[0.68rem] font-bold text-[var(--text-tertiary)]">
        <span className="absolute -translate-x-1/2" style={{ left: `${thresholdPosition}%` }}>{t("thresholdShort")} {threshold.toFixed(3)}</span>
        <span className="absolute -translate-x-1/2 text-[var(--danger)]" style={{ left: `${scorePosition}%` }}>{score.toFixed(4)}</span>
      </div>
    </div>
  );
}

function SelectBlock({ label, icon, children }: { label: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-2 flex items-center gap-2 text-sm font-semibold text-[var(--text-primary)]">{icon}{label}</span>
      <span className="relative block">{children}<ChevronDown size={16} className="pointer-events-none absolute end-4 top-1/2 -translate-y-1/2 text-[var(--text-tertiary)]" /></span>
    </label>
  );
}

function ResultMetric({ label, value, icon }: { label: string; value: string; icon: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface-muted)] p-4">
      <div className="flex items-center gap-2 text-[0.68rem] font-bold text-[var(--text-tertiary)]">{icon}{label}</div>
      <div className="mt-2 break-words font-mono text-sm font-extrabold tabular-nums text-[var(--text-primary)]">{value}</div>
    </div>
  );
}

function ReviewRow({ ok, text }: { ok: boolean; text: string }) {
  return (
    <div className="flex items-start gap-3 rounded-xl border border-[var(--border)] px-3 py-3">
      <span className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full ${ok ? "bg-[var(--success-soft)] text-[var(--success)]" : "bg-[var(--warning-soft)] text-[var(--warning)]"}`}>
        {ok ? <Check size={13} /> : <AlertTriangle size={13} />}
      </span>
      <span className="text-xs font-semibold leading-5 text-[var(--text-secondary)]">{text}</span>
    </div>
  );
}

function Feature({ icon, label }: { icon: React.ReactNode; label: string }) {
  return <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface-muted)] px-3 py-4 text-xs font-bold text-[var(--text-secondary)]"><span className="mx-auto mb-2 flex w-fit text-[var(--primary)]">{icon}</span>{label}</div>;
}

function artifactUrl(artifact?: ExplanationArtifact): string | null {
  if (!artifact?.url) return null;
  return buildArtifactUrl(artifact.url);
}

function readNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function readString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

function readStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function humanize(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}
