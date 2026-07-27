import { useMutation } from "@tanstack/react-query";
import { KeyRound, Mail, ShieldCheck, UserRound } from "lucide-react";
import { type FormEvent, useState } from "react";

import { bootstrapWorkspace, login } from "../../lib/api";
import { useI18n } from "../../lib/i18n";
import { Button } from "../ui/Button";
import { FormField } from "../ui/FormField";
import { Modal } from "../ui/Modal";

export function WorkspaceSetupModal({ open, onClose, onReady }: { open: boolean; onClose: () => void; onReady: () => void }) {
  const { t } = useI18n();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  const mutation = useMutation({
    mutationFn: async () => {
      if (password !== confirmPassword) {
        throw new Error(t("passwordsDoNotMatch"));
      }
      await bootstrapWorkspace({ email, full_name: fullName, password });
      await login(email, password);
    },
    onSuccess: onReady,
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    mutation.mutate();
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={t("initializeWorkspace")}
      description={t("initializeWorkspaceDescription")}
      maxWidth="max-w-xl"
    >
      <form onSubmit={submit} className="space-y-4">
        <div className="rounded-2xl border border-[var(--primary)]/20 bg-[var(--primary-soft)] p-4 text-sm leading-6 text-[var(--text-secondary)]">
          <div className="flex items-center gap-2 font-bold text-[var(--primary)]">
            <ShieldCheck size={18} />
            {t("firstAdministrator")}
          </div>
          <p className="mt-1.5">{t("firstAdministratorHint")}</p>
        </div>

        <FormField
          label={t("fullName")}
          value={fullName}
          onChange={(event) => setFullName(event.target.value)}
          icon={<UserRound size={18} />}
          required
          autoComplete="name"
          placeholder="Dr. Jane Smith"
        />
        <FormField
          label={t("email")}
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          icon={<Mail size={18} />}
          required
          autoComplete="email"
          placeholder="doctor@clinic.com"
        />
        <FormField
          label={t("newPassword")}
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          icon={<KeyRound size={18} />}
          required
          minLength={8}
          autoComplete="new-password"
          hint={t("passwordRequirements")}
        />
        <FormField
          label={t("confirmPassword")}
          type="password"
          value={confirmPassword}
          onChange={(event) => setConfirmPassword(event.target.value)}
          icon={<KeyRound size={18} />}
          required
          minLength={8}
          autoComplete="new-password"
        />

        {mutation.error ? (
          <div className="rounded-xl bg-[var(--danger-soft)] px-4 py-3 text-sm font-medium text-[var(--danger)]">
            {mutation.error instanceof Error ? mutation.error.message : t("requestFailed")}
          </div>
        ) : null}

        <div className="flex flex-col-reverse gap-3 pt-2 sm:flex-row sm:justify-end">
          <Button type="button" variant="secondary" onClick={onClose}>{t("cancel")}</Button>
          <Button type="submit" disabled={mutation.isPending} icon={<ShieldCheck size={17} />}>
            {mutation.isPending ? t("creatingWorkspace") : t("createAdministrator")}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
