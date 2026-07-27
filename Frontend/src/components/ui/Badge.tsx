import type { ReactNode } from "react";

interface BadgeProps {
  children: ReactNode;
  tone?: "neutral" | "primary" | "success" | "warning" | "danger" | "ai";
  dot?: boolean;
  className?: string;
}

export function Badge({ children, tone = "neutral", dot = false, className = "" }: BadgeProps) {
  const tones = {
    neutral: "bg-[var(--surface-muted)] text-[var(--text-secondary)]",
    primary: "bg-[var(--primary-soft)] text-[var(--primary)]",
    success: "bg-[var(--success-soft)] text-[var(--success)]",
    warning: "bg-[var(--warning-soft)] text-[var(--warning)]",
    danger: "bg-[var(--danger-soft)] text-[var(--danger)]",
    ai: "bg-[var(--ai-soft)] text-[var(--ai-accent)]",
  };

  const dots = {
    neutral: "bg-[var(--text-tertiary)]",
    primary: "bg-[var(--primary)]",
    success: "bg-[var(--success)]",
    warning: "bg-[var(--warning)]",
    danger: "bg-[var(--danger)]",
    ai: "bg-[var(--ai-accent)]",
  };

  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ${tones[tone]} ${className}`}>
      {dot ? <span className={`h-1.5 w-1.5 rounded-full ${dots[tone]}`} /> : null}
      {children}
    </span>
  );
}
