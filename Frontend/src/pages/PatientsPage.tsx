import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { CalendarDays, ChevronRight, IdCard, Phone, Plus, Search, UserRound, UsersRound } from "lucide-react";
import { type ReactNode, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { PatientFormModal } from "../components/patients/PatientFormModal";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { PageHeader } from "../components/ui/PageHeader";
import { useAuthStore } from "../features/auth/auth-store";
import { listPatients } from "../lib/api";
import { formatDate } from "../lib/format";
import { useI18n } from "../lib/i18n";
import { previewPatients } from "../lib/preview-data";
import type { Patient } from "../lib/types";

function patientAge(dateOfBirth: string | null): string {
  if (!dateOfBirth) return "—";
  const birth = new Date(dateOfBirth);
  if (Number.isNaN(birth.getTime())) return "—";
  const today = new Date();
  let age = today.getFullYear() - birth.getFullYear();
  const beforeBirthday = today.getMonth() < birth.getMonth() || (today.getMonth() === birth.getMonth() && today.getDate() < birth.getDate());
  if (beforeBirthday) age -= 1;
  return String(age);
}

export function PatientsPage() {
  const { t, language } = useI18n();
  const navigate = useNavigate();
  const previewMode = useAuthStore((state) => state.previewMode);
  const [search, setSearch] = useState("");
  const [createOpen, setCreateOpen] = useState(false);

  const query = useQuery({
    queryKey: ["patients", search],
    queryFn: () => listPatients(search),
    enabled: !previewMode,
  });

  const patients = useMemo(() => {
    if (!previewMode) return query.data || [];
    const token = search.trim().toLowerCase();
    if (!token) return previewPatients;
    return previewPatients.filter((patient) =>
      [patient.display_id, patient.medical_record_number, patient.first_name, patient.last_name]
        .join(" ")
        .toLowerCase()
        .includes(token),
    );
  }, [previewMode, query.data, search]);

  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
      <PageHeader
        eyebrow={t("patientRegistry")}
        title={t("patients")}
        description={t("patientsDescription")}
        actions={
          <Button icon={<Plus size={17} />} onClick={() => setCreateOpen(true)} disabled={previewMode} title={previewMode ? t("previewActionDisabled") : undefined}>
            {t("addPatient")}
          </Button>
        }
      />

      <Card className="mb-5 p-4 sm:p-5">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="relative w-full max-w-xl">
            <Search size={18} className="pointer-events-none absolute start-4 top-1/2 -translate-y-1/2 text-[var(--text-tertiary)]" />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder={t("searchPatients")}
              className="h-12 w-full rounded-xl border border-[var(--border)] bg-[var(--surface-muted)] ps-11 pe-4 text-sm text-[var(--text-primary)] outline-none transition-all placeholder:text-[var(--text-tertiary)] focus:border-[var(--primary)] focus:ring-4 focus:ring-[var(--primary-soft)]"
            />
          </div>
          <div className="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
            <UsersRound size={18} className="text-[var(--primary)]" />
            <span className="font-bold tabular-nums text-[var(--text-primary)]">{patients.length}</span>
            <span>{t("patientRecords")}</span>
          </div>
        </div>
      </Card>

      {query.isLoading && !previewMode ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, index) => <div key={index} className="h-56 animate-pulse rounded-2xl bg-[var(--surface-muted)]" />)}
        </div>
      ) : patients.length ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {patients.map((patient, index) => (
            <PatientCard
              key={patient.id}
              patient={patient}
              index={index}
              language={language}
              onOpen={() => navigate(`/patients/${encodeURIComponent(patient.display_id)}`)}
            />
          ))}
        </div>
      ) : (
        <EmptyState
          icon={<UserRound size={25} />}
          title={t("noPatients")}
          description={search ? t("noPatientsSearch") : t("noPatientsDescription")}
          action={!previewMode && !search ? <Button icon={<Plus size={17} />} onClick={() => setCreateOpen(true)}>{t("addPatient")}</Button> : undefined}
        />
      )}

      {query.error ? (
        <div className="mt-5 rounded-2xl bg-[var(--danger-soft)] px-4 py-3 text-sm font-medium text-[var(--danger)]">
          {query.error instanceof Error ? query.error.message : t("requestFailed")}
        </div>
      ) : null}

      <PatientFormModal open={createOpen} onClose={() => setCreateOpen(false)} />
    </motion.div>
  );
}

function PatientCard({ patient, index, language, onOpen }: { patient: Patient; index: number; language: "en" | "ar"; onOpen: () => void }) {
  const { t } = useI18n();
  const initials = `${patient.first_name[0] || ""}${patient.last_name[0] || ""}`.toUpperCase();

  return (
    <motion.button
      type="button"
      onClick={onOpen}
      className="text-start"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: Math.min(index * 0.04, 0.24) }}
    >
      <Card interactive className="h-full overflow-hidden p-5">
        <div className="flex items-start justify-between gap-4">
          <div className="flex min-w-0 items-center gap-3">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-[linear-gradient(135deg,var(--primary-soft),var(--ai-soft))] text-sm font-extrabold text-[var(--primary)]">
              {initials}
            </div>
            <div className="min-w-0">
              <div className="truncate text-base font-extrabold text-[var(--text-primary)]">{patient.first_name} {patient.last_name}</div>
              <div className="mt-1 flex items-center gap-1.5 text-xs text-[var(--text-tertiary)]">
                <IdCard size={13} />
                {patient.display_id}
              </div>
            </div>
          </div>
          <ChevronRight size={18} className={`mt-1 shrink-0 text-[var(--text-tertiary)] ${language === "ar" ? "rotate-180" : ""}`} />
        </div>

        <div className="mt-5 grid grid-cols-2 gap-3">
          <Info label={t("age")} value={`${patientAge(patient.date_of_birth)} ${t("years")}`} icon={<CalendarDays size={15} />} />
          <Info label={t("medicalRecordNumber")} value={patient.medical_record_number} icon={<IdCard size={15} />} />
        </div>

        <div className="mt-4 flex min-h-8 items-center justify-between gap-3 border-t border-[var(--border)] pt-4">
          <div className="flex min-w-0 items-center gap-2 text-xs text-[var(--text-secondary)]">
            <Phone size={14} className="shrink-0 text-[var(--text-tertiary)]" />
            <span className="truncate">{patient.phone || t("noPhone")}</span>
          </div>
          <Badge tone="neutral">{formatDate(patient.updated_at, language)}</Badge>
        </div>
      </Card>
    </motion.button>
  );
}

function Info({ label, value, icon }: { label: string; value: string; icon: ReactNode }) {
  return (
    <div className="rounded-xl bg-[var(--surface-muted)] p-3">
      <div className="flex items-center gap-1.5 text-[0.68rem] font-semibold text-[var(--text-tertiary)]">{icon}{label}</div>
      <div className="mt-1.5 truncate text-xs font-bold text-[var(--text-primary)]">{value}</div>
    </div>
  );
}
