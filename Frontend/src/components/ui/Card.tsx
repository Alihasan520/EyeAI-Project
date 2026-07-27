import type { HTMLAttributes, ReactNode } from "react";

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
  interactive?: boolean;
}

export function Card({ children, interactive = false, className = "", ...props }: CardProps) {
  return (
    <div
      className={`surface-card rounded-2xl border border-[var(--border)] bg-[var(--surface)] shadow-[var(--shadow-card)] ${interactive ? "transition-all duration-200 hover:-translate-y-0.5 hover:border-[var(--primary)]/35 hover:shadow-[var(--shadow-card-hover)]" : ""} ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}
