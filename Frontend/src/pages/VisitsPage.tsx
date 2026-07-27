import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { CalendarDays, ChevronRight, Eye, Search, Stethoscope } from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { Badge } from "../components/ui/Badge";
import { Card } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { PageHeader } from "../components/ui/PageHeader";
import { SegmentedControl } from "../components/ui/SegmentedControl";
import { useAuthStore } from "../features/auth/auth-store";
import { listVisits } from "../lib/api";
import { formatDate } from "../lib/format";
import { useI18n } from "../lib/i18n";
import { previewVisits } from "../lib/preview-data";
import type { EyeSide, VisitListItem } from "../lib/types";

export function VisitsPage() {
  const { t, language } = useI18n();
  const navigate = useNavigate();
  const previewMode = useAuthStore((state) => state.previewMode);
  const [search, setSearch] = useState("");
  const [eye, setEye] = useState<"all" | EyeSide>("all");

  const query = useQuery({
    queryKey: ["visits", eye],
    queryFn: () => listVisits({ eye: eye === "all" ? undefined : eye }),
    enabled: !previewMode,
  });

  const visits = useMemo(() => {
    const source = previewMode ? previewVisits : query.data || [];
    const eyeFiltered = eye === "all" ? source : source.filter((item) => item.visit.eye === eye);
    const token = search.trim().toLowerCase();
    if (!token) return eyeFiltered;
    return eyeFiltered.filter((item) =>
      [item.visit.display_id, item.patient_display_id, item.patient_name]
        .join(" ")
        .toLowerCase()
        .includes(token),
    );
  }, [eye, previewMode, query.data, search]);

  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
      <PageHeader
        eyebrow={t("longitudinalCare")}
        title={t("visits")}
        description={t("visitsDescription")}
      />

      <Card className="mb-5 p-4 sm:p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="relative w-full max-w-xl">
            <Search size={18} className="pointer-events-none absolute start-4 top-1/2 -translate-y-1/2 text-[var(--text-tertiary)]" />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder={t("searchVisits")}
              className="h-12 w-full rounded-xl border border-[var(--border)] bg-[var(--surface-muted)] ps-11 pe-4 text-sm text-[var(--text-primary)] outline-none transition-all placeholder:text-[var(--text-tertiary)] focus:border-[var(--primary)] focus:ring-4 focus:ring-[var(--primary-soft)]"
            />
          </div>
          <SegmentedControl
            value={eye}
            options={[
              { value: "all", label: t("allEyes") },
              { value: "right", label: t("rightEye") },
              { value: "left", label: t("leftEye") },
            ]}
            onChange={setEye}
          />
        </div>
      </Card>

      {query.isLoading && !previewMode ? (
        <div className="space-y-3">{Array.from({ length: 5 }).map((_, index) => <div key={index} className="h-24 animate-pulse rounded-2xl bg-[var(--surface-muted)]" />)}</div>
      ) : visits.length ? (
        <div className="space-y-3">
          {visits.map((item, index) => <VisitRow key={item.visit.id} item={item} index={index} language={language} onOpen={() => navigate(`/patients/${encodeURIComponent(item.patient_display_id)}`)} />)}
        </div>
      ) : (
        <EmptyState icon={<Stethoscope size={25} />} title={t("noVisits")} description={t("noVisitsDescription")} />
      )}

      {query.error ? (
        <div className="mt-5 rounded-2xl bg-[var(--danger-soft)] px-4 py-3 text-sm font-medium text-[var(--danger)]">
          {query.error instanceof Error ? query.error.message : t("requestFailed")}
        </div>
      ) : null}
    </motion.div>
  );
}

function VisitRow({ item, index, language, onOpen }: { item: VisitListItem; index: number; language: "en" | "ar"; onOpen: () => void }) {
  const { t } = useI18n();
  return (
    <motion.button type="button" onClick={onOpen} className="w-full text-start" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: Math.min(index * 0.035, 0.22) }}>
      <Card interactive className="p-4 sm:p-5">
        <div className="flex items-center gap-4">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-[linear-gradient(135deg,var(--primary-soft),var(--ai-soft))] text-[var(--primary)]">
            <Eye size={21} />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-extrabold text-[var(--text-primary)]">{item.patient_name}</span>
              <Badge tone="neutral">{item.patient_display_id}</Badge>
              <Badge tone="primary">{item.visit.eye === "right" ? t("rightEye") : t("leftEye")}</Badge>
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-[var(--text-tertiary)]">
              <span className="inline-flex items-center gap-1.5"><CalendarDays size={14} />{formatDate(item.visit.visit_date, language)}</span>
              <span>{item.visit.display_id}</span>
            </div>
            {item.visit.notes ? <p className="mt-2 truncate text-sm text-[var(--text-secondary)]">{item.visit.notes}</p> : null}
          </div>
          <ChevronRight size={19} className={`shrink-0 text-[var(--text-tertiary)] ${language === "ar" ? "rotate-180" : ""}`} />
        </div>
      </Card>
    </motion.button>
  );
}
