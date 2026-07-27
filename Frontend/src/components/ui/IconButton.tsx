import type { ButtonHTMLAttributes, ReactNode } from "react";

interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  label: string;
  children: ReactNode;
  active?: boolean;
}

export function IconButton({ label, children, active = false, className = "", ...props }: IconButtonProps) {
  return (
    <button
      aria-label={label}
      title={label}
      className={`inline-flex h-10 w-10 items-center justify-center rounded-xl border transition-all duration-200 ${active ? "border-[var(--primary)]/45 bg-[var(--primary-soft)] text-[var(--primary)]" : "border-transparent text-[var(--text-secondary)] hover:border-[var(--border)] hover:bg-[var(--surface-hover)] hover:text-[var(--text-primary)]"} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}
