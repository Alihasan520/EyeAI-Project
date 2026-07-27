import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CalendarClock, FileText } from "lucide-react";
import { type FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";

import { createVisit } from "../../lib/api";
import { useI18n } from "../../lib/i18n";
import type { EyeSide } from "../../lib/types";
import { Button } from "../ui/Button";
import { FormField } from "../ui/FormField";
import { Modal } from "../ui/Modal";
import { SegmentedControl } from "../ui/SegmentedControl";

export function VisitFormModal({ open, onClose, patientRef, patientName }: { open: boolean; onClose: () => void; patientRef: string; patientName: string }) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [eye, setEye] = useState<EyeSide>("right");
  const [visitDate, setVisitDate] = useState("");
  const [notes, setNotes] = useState("");

  const mutation = useMutation({
    mutationFn: () => createVisit(patientRef, {
      eye,
      visit_date: visitDate ? new Date(visitDate).toISOString() : null,
      notes: notes.trim() || null,
    }),
    onSuccess: (visit) => {
      queryClient.invalidateQueries({ queryKey: ["timeline", patientRef] });
      queryClient.invalidateQueries({ queryKey: ["visits"] });
      onClose();
      navigate(`/analysis?visit=${encodeURIComponent(visit.display_id)}&patient=${encodeURIComponent(patientRef)}`);
    },
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    mutation.mutate();
  }

  return (
    <Modal open={open} onClose={onClose} title={t("newVisit")} description={`${patientName} · ${patientRef}`} maxWidth="max-w-xl">
      <form onSubmit={submit} className="space-y-5">
        <div>
          <div className="mb-2 text-sm font-semibold text-[var(--text-primary)]">{t("selectEye")}</div>
          <SegmentedControl
            value={eye}
            options={[
              { value: "right", label: t("rightEye") },
              { value: "left", label: t("leftEye") },
            ]}
            onChange={setEye}
          />
        </div>
        <FormField
          label={t("visitDate")}
          type="datetime-local"
          value={visitDate}
          onChange={(event) => setVisitDate(event.target.value)}
          icon={<CalendarClock size={18} />}
          hint={t("visitDateHint")}
        />
        <FormField
          multiline
          label={t("visitNotes")}
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
          icon={<FileText size={18} />}
          placeholder={t("visitNotesPlaceholder")}
        />
        {mutation.error ? (
          <div className="rounded-xl bg-[var(--danger-soft)] px-4 py-3 text-sm font-medium text-[var(--danger)]">
            {mutation.error instanceof Error ? mutation.error.message : t("requestFailed")}
          </div>
        ) : null}
        <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
          <Button type="button" variant="secondary" onClick={onClose}>{t("cancel")}</Button>
          <Button type="submit" disabled={mutation.isPending}>{mutation.isPending ? t("saving") : t("createVisit")}</Button>
        </div>
      </form>
    </Modal>
  );
}
