import type { ReactNode } from "react";

export function PageHeader({ eyebrow, title, description, actions }: { eyebrow?: string; title: string; description: string; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div className="max-w-3xl">
        {eyebrow ? <div className="mb-2 text-xs font-extrabold uppercase tracking-[0.18em] text-[var(--primary)]">{eyebrow}</div> : null}
        <h2 className="text-2xl font-extrabold tracking-[-0.035em] text-[var(--text-primary)] sm:text-3xl">{title}</h2>
        <p className="mt-2 text-sm leading-7 text-[var(--text-secondary)]">{description}</p>
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </div>
  );
}
