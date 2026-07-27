import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, Mail, MoreHorizontal, Plus, ShieldCheck, UserCheck, UserRound, UserX } from "lucide-react";
import { type FormEvent, useState } from "react";

import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { FormField } from "../components/ui/FormField";
import { Modal } from "../components/ui/Modal";
import { PageHeader } from "../components/ui/PageHeader";
import { useAuthStore } from "../features/auth/auth-store";
import { createUser, listUsers, resetUserPassword, updateUserAccount } from "../lib/api";
import { formatDate } from "../lib/format";
import { useI18n } from "../lib/i18n";
import { previewUsers } from "../lib/preview-data";
import type { User } from "../lib/types";

export function UsersAccessPage() {
  const { t, language } = useI18n();
  const currentUser = useAuthStore((state) => state.user);
  const previewMode = useAuthStore((state) => state.previewMode);
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [selected, setSelected] = useState<User | null>(null);

  const query = useQuery({ queryKey: ["users"], queryFn: listUsers, enabled: !previewMode && currentUser?.role === "admin" });
  const users = previewMode ? previewUsers : query.data || [];

  const toggleMutation = useMutation({
    mutationFn: (user: User) => updateUserAccount(user.display_id, { is_active: !user.is_active }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["users"] }),
  });

  if (currentUser?.role !== "admin") {
    return <EmptyState icon={<ShieldCheck size={25} />} title={t("adminAccessRequired")} description={t("adminAccessRequiredDescription")} />;
  }

  return (
    <div>
      <PageHeader
        eyebrow={t("administration")}
        title={t("usersAndAccess")}
        description={t("usersAndAccessDescription")}
        actions={<Button icon={<Plus size={17} />} onClick={() => setCreateOpen(true)} disabled={previewMode}>{t("addUser")}</Button>}
      />

      <Card className="overflow-hidden">
        <div className="hidden grid-cols-[minmax(220px,1.2fr)_minmax(220px,1fr)_130px_130px_64px] gap-4 border-b border-[var(--border)] bg-[var(--surface-muted)] px-5 py-3 text-[0.68rem] font-extrabold uppercase tracking-[0.14em] text-[var(--text-tertiary)] lg:grid">
          <span>{t("user")}</span><span>{t("email")}</span><span>{t("role")}</span><span>{t("status")}</span><span />
        </div>
        <div className="divide-y divide-[var(--border)]">
          {users.map((user) => (
            <div key={user.id} className="grid gap-4 px-5 py-4 lg:grid-cols-[minmax(220px,1.2fr)_minmax(220px,1fr)_130px_130px_64px] lg:items-center">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[linear-gradient(135deg,var(--primary-soft),var(--ai-soft))] text-xs font-extrabold text-[var(--primary)]">
                  {user.full_name.split(" ").slice(0, 2).map((part) => part[0]?.toUpperCase()).join("")}
                </div>
                <div className="min-w-0"><div className="truncate text-sm font-extrabold text-[var(--text-primary)]">{user.full_name}</div><div className="mt-1 text-xs text-[var(--text-tertiary)]">{user.display_id} · {formatDate(user.created_at, language)}</div></div>
              </div>
              <div className="truncate text-sm text-[var(--text-secondary)]">{user.email}</div>
              <Badge tone={user.role === "admin" ? "primary" : "neutral"}>{user.role === "admin" ? t("roleAdmin") : t("roleClinician")}</Badge>
              <Badge tone={user.is_active ? "success" : "danger"} dot>{user.is_active ? t("active") : t("inactive")}</Badge>
              <div className="flex justify-end">
                <button type="button" onClick={() => setSelected(user)} className="rounded-xl p-2 text-[var(--text-tertiary)] hover:bg-[var(--surface-hover)] hover:text-[var(--text-primary)]"><MoreHorizontal size={19} /></button>
              </div>
            </div>
          ))}
        </div>
      </Card>

      {query.isLoading && !previewMode ? <div className="mt-4 h-28 animate-pulse rounded-2xl bg-[var(--surface-muted)]" /> : null}
      {query.error ? <div className="mt-4 rounded-2xl bg-[var(--danger-soft)] px-4 py-3 text-sm font-medium text-[var(--danger)]">{query.error instanceof Error ? query.error.message : t("requestFailed")}</div> : null}

      <CreateUserModal open={createOpen} onClose={() => setCreateOpen(false)} />
      <UserActionsModal
        user={selected}
        onClose={() => setSelected(null)}
        onToggle={() => {
          if (selected && !previewMode) toggleMutation.mutate(selected);
          setSelected(null);
        }}
      />
    </div>
  );
}

function CreateUserModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<"admin" | "clinician">("clinician");

  const mutation = useMutation({
    mutationFn: () => createUser({ full_name: fullName.trim(), email: email.trim(), password, role }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      setFullName(""); setEmail(""); setPassword(""); setRole("clinician"); onClose();
    },
  });

  function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); mutation.mutate(); }

  return (
    <Modal open={open} onClose={onClose} title={t("addUser")} description={t("addUserDescription")} maxWidth="max-w-xl">
      <form className="space-y-4" onSubmit={submit}>
        <FormField label={t("fullName")} value={fullName} onChange={(event) => setFullName(event.target.value)} icon={<UserRound size={18} />} required />
        <FormField label={t("email")} type="email" value={email} onChange={(event) => setEmail(event.target.value)} icon={<Mail size={18} />} required />
        <FormField label={t("temporaryPassword")} type="password" value={password} onChange={(event) => setPassword(event.target.value)} icon={<KeyRound size={18} />} required minLength={8} hint={t("temporaryPasswordHint")} />
        <label className="block"><span className="mb-2 block text-sm font-semibold text-[var(--text-primary)]">{t("role")}</span><select value={role} onChange={(event) => setRole(event.target.value as "admin" | "clinician")} className="h-12 w-full rounded-xl border border-[var(--border)] bg-[var(--surface-muted)] px-4 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--primary)] focus:ring-4 focus:ring-[var(--primary-soft)]"><option value="clinician">{t("roleClinician")}</option><option value="admin">{t("roleAdmin")}</option></select></label>
        {mutation.error ? <div className="rounded-xl bg-[var(--danger-soft)] px-4 py-3 text-sm font-medium text-[var(--danger)]">{mutation.error instanceof Error ? mutation.error.message : t("requestFailed")}</div> : null}
        <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end"><Button type="button" variant="secondary" onClick={onClose}>{t("cancel")}</Button><Button type="submit" disabled={mutation.isPending || !fullName || !email || password.length < 8}>{mutation.isPending ? t("saving") : t("createUser")}</Button></div>
      </form>
    </Modal>
  );
}

function UserActionsModal({ user, onClose, onToggle }: { user: User | null; onClose: () => void; onToggle: () => void }) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [password, setPassword] = useState("");
  const resetMutation = useMutation({
    mutationFn: () => resetUserPassword(user!.display_id, password),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["users"] }); setPassword(""); onClose(); },
  });

  return (
    <Modal open={Boolean(user)} onClose={onClose} title={user?.full_name || t("userActions")} description={user?.email} maxWidth="max-w-lg">
      {user ? <div className="space-y-5">
        <div className="grid grid-cols-2 gap-3"><div className="rounded-xl bg-[var(--surface-muted)] p-3"><div className="text-xs text-[var(--text-tertiary)]">{t("role")}</div><div className="mt-1 text-sm font-bold text-[var(--text-primary)]">{user.role === "admin" ? t("roleAdmin") : t("roleClinician")}</div></div><div className="rounded-xl bg-[var(--surface-muted)] p-3"><div className="text-xs text-[var(--text-tertiary)]">{t("status")}</div><div className="mt-1 text-sm font-bold text-[var(--text-primary)]">{user.is_active ? t("active") : t("inactive")}</div></div></div>
        <div><div className="mb-2 text-sm font-semibold text-[var(--text-primary)]">{t("resetPassword")}</div><div className="flex gap-2"><input type="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder={t("newPassword")} className="h-11 min-w-0 flex-1 rounded-xl border border-[var(--border)] bg-[var(--surface-muted)] px-4 text-sm outline-none focus:border-[var(--primary)] focus:ring-4 focus:ring-[var(--primary-soft)]" /><Button size="sm" variant="secondary" onClick={() => resetMutation.mutate()} disabled={password.length < 8 || resetMutation.isPending}>{t("reset")}</Button></div></div>
        <button type="button" onClick={onToggle} className={`flex w-full items-center gap-3 rounded-2xl px-4 py-3 text-start text-sm font-bold ${user.is_active ? "bg-[var(--danger-soft)] text-[var(--danger)]" : "bg-[var(--success-soft)] text-[var(--success)]"}`}>{user.is_active ? <UserX size={18} /> : <UserCheck size={18} />}{user.is_active ? t("disableAccount") : t("enableAccount")}</button>
      </div> : null}
    </Modal>
  );
}
