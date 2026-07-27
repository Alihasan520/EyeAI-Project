import type { ReactNode } from "react";

export function EmptyState({ icon, title, description, action }: { icon: ReactNode; title: string; description: string; action?: ReactNode }) {
  return (
    <div className="flex min-h-64 flex-col items-center justify-center rounded-3xl border border-dashed border-[var(--border)] bg-[var(--surface-muted)] px-6 py-12 text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-[linear-gradient(135deg,var(--primary-soft),var(--ai-soft))] text-[var(--primary)]">{icon}</div>
      <h3 className="mt-5 text-lg font-bold text-[var(--text-primary)]">{title}</h3>
      <p className="mt-2 max-w-md text-sm leading-6 text-[var(--text-secondary)]">{description}</p>
      {action ? <div className="mt-6">{action}</div> : null}
    </div>
  );
}
