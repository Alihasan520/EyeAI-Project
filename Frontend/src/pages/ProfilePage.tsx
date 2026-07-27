import { useMutation } from "@tanstack/react-query";
import { KeyRound, Mail, Save, ShieldCheck, UserRound } from "lucide-react";
import { type FormEvent, useEffect, useState } from "react";

import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { FormField } from "../components/ui/FormField";
import { PageHeader } from "../components/ui/PageHeader";
import { useAuthStore } from "../features/auth/auth-store";
import { changeMyPassword, updateMyProfile } from "../lib/api";
import { useI18n } from "../lib/i18n";

export function ProfilePage() {
  const { t } = useI18n();
  const user = useAuthStore((state) => state.user);
  const updateUser = useAuthStore((state) => state.updateUser);
  const clearSession = useAuthStore((state) => state.clearSession);
  const previewMode = useAuthStore((state) => state.previewMode);
  const [fullName, setFullName] = useState(user?.full_name || "");
  const [email, setEmail] = useState(user?.email || "");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [profileMessage, setProfileMessage] = useState("");
  const [passwordMessage, setPasswordMessage] = useState("");

  useEffect(() => {
    setFullName(user?.full_name || "");
    setEmail(user?.email || "");
  }, [user]);

  const profileMutation = useMutation({
    mutationFn: () => updateMyProfile({ full_name: fullName.trim(), email: email.trim() }),
    onSuccess: (updated) => {
      updateUser(updated);
      setProfileMessage(t("profileUpdated"));
    },
  });

  const passwordMutation = useMutation({
    mutationFn: async () => {
      if (newPassword !== confirmPassword) throw new Error(t("passwordsDoNotMatch"));
      await changeMyPassword({ current_password: currentPassword, new_password: newPassword });
    },
    onSuccess: () => {
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setPasswordMessage(t("passwordChanged"));
      window.setTimeout(clearSession, 1400);
    },
  });

  function submitProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setProfileMessage("");
    profileMutation.mutate();
  }

  function submitPassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPasswordMessage("");
    passwordMutation.mutate();
  }

  return (
    <div>
      <PageHeader eyebrow={t("accountSettings")} title={t("myProfile")} description={t("myProfileDescription")} />

      <div className="grid gap-6 xl:grid-cols-[0.92fr_1.08fr]">
        <Card className="p-5 sm:p-6">
          <div className="flex items-center gap-4 border-b border-[var(--border)] pb-5">
            <div className="flex h-16 w-16 items-center justify-center rounded-3xl bg-[linear-gradient(135deg,var(--primary),var(--ai-accent))] text-lg font-extrabold text-white">
              {user?.full_name.split(" ").slice(0, 2).map((part) => part[0]?.toUpperCase()).join("") || "EA"}
            </div>
            <div className="min-w-0">
              <div className="truncate text-xl font-extrabold text-[var(--text-primary)]">{user?.full_name}</div>
              <div className="mt-1 truncate text-sm text-[var(--text-secondary)]">{user?.email}</div>
              <div className="mt-2 inline-flex items-center gap-1.5 rounded-full bg-[var(--primary-soft)] px-3 py-1 text-xs font-bold text-[var(--primary)]">
                <ShieldCheck size={14} />
                {user?.role === "admin" ? t("roleAdmin") : t("roleClinician")}
              </div>
            </div>
          </div>

          <form className="mt-5 space-y-4" onSubmit={submitProfile}>
            <FormField label={t("fullName")} value={fullName} onChange={(event) => setFullName(event.target.value)} icon={<UserRound size={18} />} required disabled={previewMode} />
            <FormField label={t("email")} type="email" value={email} onChange={(event) => setEmail(event.target.value)} icon={<Mail size={18} />} required disabled={previewMode} />

            {profileMessage ? <div className="rounded-xl bg-[var(--success-soft)] px-4 py-3 text-sm font-medium text-[var(--success)]">{profileMessage}</div> : null}
            {profileMutation.error ? <div className="rounded-xl bg-[var(--danger-soft)] px-4 py-3 text-sm font-medium text-[var(--danger)]">{profileMutation.error instanceof Error ? profileMutation.error.message : t("requestFailed")}</div> : null}

            <Button type="submit" icon={<Save size={17} />} disabled={previewMode || profileMutation.isPending || !fullName.trim() || !email.trim()}>
              {profileMutation.isPending ? t("saving") : t("saveChanges")}
            </Button>
          </form>
        </Card>

        <Card className="p-5 sm:p-6">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[var(--ai-soft)] text-[var(--ai-accent)]"><KeyRound size={20} /></div>
            <div>
              <h3 className="font-extrabold text-[var(--text-primary)]">{t("changePassword")}</h3>
              <p className="mt-1 text-sm text-[var(--text-secondary)]">{t("changePasswordDescription")}</p>
            </div>
          </div>

          <form className="mt-6 space-y-4" onSubmit={submitPassword}>
            <FormField label={t("currentPassword")} type="password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} icon={<KeyRound size={18} />} required minLength={8} disabled={previewMode} autoComplete="current-password" />
            <FormField label={t("newPassword")} type="password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} icon={<KeyRound size={18} />} required minLength={8} disabled={previewMode} autoComplete="new-password" hint={t("passwordRequirements")} />
            <FormField label={t("confirmPassword")} type="password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} icon={<KeyRound size={18} />} required minLength={8} disabled={previewMode} autoComplete="new-password" />

            {passwordMessage ? <div className="rounded-xl bg-[var(--success-soft)] px-4 py-3 text-sm font-medium text-[var(--success)]">{passwordMessage}</div> : null}
            {passwordMutation.error ? <div className="rounded-xl bg-[var(--danger-soft)] px-4 py-3 text-sm font-medium text-[var(--danger)]">{passwordMutation.error instanceof Error ? passwordMutation.error.message : t("requestFailed")}</div> : null}

            <Button type="submit" icon={<KeyRound size={17} />} disabled={previewMode || passwordMutation.isPending || !currentPassword || !newPassword || !confirmPassword}>
              {passwordMutation.isPending ? t("saving") : t("updatePassword")}
            </Button>
          </form>
        </Card>
      </div>

      {previewMode ? <div className="mt-5 rounded-2xl bg-[var(--warning-soft)] px-4 py-3 text-sm text-[var(--warning)]">{t("previewActionDisabled")}</div> : null}
    </div>
  );
}
