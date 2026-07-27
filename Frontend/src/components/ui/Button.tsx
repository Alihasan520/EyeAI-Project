import type { ButtonHTMLAttributes, ReactNode } from "react";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md" | "lg";
  icon?: ReactNode;
  fullWidth?: boolean;
}

export function Button({
  variant = "primary",
  size = "md",
  icon,
  fullWidth = false,
  className = "",
  children,
  ...props
}: ButtonProps) {
  const variants = {
    primary:
      "bg-[linear-gradient(135deg,var(--primary),var(--ai-accent))] text-white shadow-[0_12px_30px_-16px_var(--primary)] hover:brightness-110",
    secondary:
      "border border-[var(--border)] bg-[var(--surface-raised)] text-[var(--text-primary)] hover:border-[var(--primary)]/60 hover:bg-[var(--surface-hover)]",
    ghost:
      "text-[var(--text-secondary)] hover:bg-[var(--surface-hover)] hover:text-[var(--text-primary)]",
    danger:
      "bg-[var(--danger-soft)] text-[var(--danger)] hover:bg-[var(--danger)] hover:text-white",
  };

  const sizes = {
    sm: "h-9 px-3 text-sm",
    md: "h-11 px-4 text-sm",
    lg: "h-12 px-5 text-base",
  };

  return (
    <button
      className={`inline-flex items-center justify-center gap-2 rounded-xl font-semibold transition-all duration-200 disabled:cursor-not-allowed disabled:opacity-55 ${variants[variant]} ${sizes[size]} ${fullWidth ? "w-full" : ""} ${className}`}
      {...props}
    >
      {icon}
      {children}
    </button>
  );
}
