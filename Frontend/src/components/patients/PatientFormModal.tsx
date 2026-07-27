import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CalendarDays, FileText, IdCard, Phone, UserRound } from "lucide-react";
import { type FormEvent, useEffect, useState } from "react";

import { createPatient, updatePatient } from "../../lib/api";
import { useI18n } from "../../lib/i18n";
import type { Patient } from "../../lib/types";
import { Button } from "../ui/Button";
import { FormField } from "../ui/FormField";
import { Modal } from "../ui/Modal";

interface PatientFormModalProps {
  open: boolean;
  onClose: () => void;
  patient?: Patient | null;
  onSaved?: (patient: Patient) => void;
}

export function PatientFormModal({ open, onClose, patient, onSaved }: PatientFormModalProps) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [medicalRecordNumber, setMedicalRecordNumber] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [dateOfBirth, setDateOfBirth] = useState("");
  const [sex, setSex] = useState("");
  const [phone, setPhone] = useState("");
  const [notes, setNotes] = useState("");

  useEffect(() => {
    if (!open) return;
    setMedicalRecordNumber(patient?.medical_record_number || "");
    setFirstName(patient?.first_name || "");
    setLastName(patient?.last_name || "");
    setDateOfBirth(patient?.date_of_birth || "");
    setSex(patient?.sex || "");
    setPhone(patient?.phone || "");
    setNotes(patient?.notes || "");
  }, [open, patient]);

  const mutation = useMutation({
    mutationFn: () => {
      const common = {
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        date_of_birth: dateOfBirth || null,
        sex: sex || null,
        phone: phone.trim() || null,
        notes: notes.trim() || null,
      };
      return patient
        ? updatePatient(patient.display_id, common)
        : createPatient({ medical_record_number: medicalRecordNumber.trim(), ...common });
    },
    onSuccess: (saved) => {
      queryClient.invalidateQueries({ queryKey: ["patients"] });
      queryClient.invalidateQueries({ queryKey: ["patient", saved.display_id] });
      onSaved?.(saved);
      onClose();
    },
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    mutation.mutate();
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={patient ? t("editPatient") : t("addPatient")}
      description={patient ? t("editPatientDescription") : t("addPatientDescription")}
    >
      <form onSubmit={submit} className="space-y-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField
            label={t("medicalRecordNumber")}
            value={medicalRecordNumber}
            onChange={(event) => setMedicalRecordNumber(event.target.value)}
            icon={<IdCard size={18} />}
            required
            disabled={Boolean(patient)}
            placeholder="MRN-240001"
          />
          <label className="block">
            <span className="mb-2 block text-sm font-semibold text-[var(--text-primary)]">{t("sex")}</span>
            <select
              value={sex}
              onChange={(event) => setSex(event.target.value)}
              className="h-12 w-full rounded-xl border border-[var(--border)] bg-[var(--surface-muted)] px-4 text-sm text-[var(--text-primary)] outline-none transition-all focus:border-[var(--primary)] focus:ring-4 focus:ring-[var(--primary-soft)]"
            >
              <option value="">{t("notSpecified")}</option>
              <option value="female">{t("female")}</option>
              <option value="male">{t("male")}</option>
              <option value="other">{t("other")}</option>
            </select>
          </label>
          <FormField
            label={t("firstName")}
            value={firstName}
            onChange={(event) => setFirstName(event.target.value)}
            icon={<UserRound size={18} />}
            required
          />
          <FormField
            label={t("lastName")}
            value={lastName}
            onChange={(event) => setLastName(event.target.value)}
            icon={<UserRound size={18} />}
            required
          />
          <FormField
            label={t("dateOfBirth")}
            type="date"
            value={dateOfBirth}
            onChange={(event) => setDateOfBirth(event.target.value)}
            icon={<CalendarDays size={18} />}
          />
          <FormField
            label={t("phone")}
            value={phone}
            onChange={(event) => setPhone(event.target.value)}
            icon={<Phone size={18} />}
            placeholder="+1 555 000 000"
          />
        </div>
        <FormField
          multiline
          label={t("patientNotes")}
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
          icon={<FileText size={18} />}
          placeholder={t("patientNotesPlaceholder")}
        />

        {mutation.error ? (
          <div className="rounded-xl bg-[var(--danger-soft)] px-4 py-3 text-sm font-medium text-[var(--danger)]">
            {mutation.error instanceof Error ? mutation.error.message : t("requestFailed")}
          </div>
        ) : null}

        <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
          <Button type="button" variant="secondary" onClick={onClose}>{t("cancel")}</Button>
          <Button type="submit" disabled={mutation.isPending || !firstName.trim() || !lastName.trim() || (!patient && !medicalRecordNumber.trim())}>
            {mutation.isPending ? t("saving") : t("savePatient")}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
