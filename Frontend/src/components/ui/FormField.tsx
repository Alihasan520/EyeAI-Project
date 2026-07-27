import type { InputHTMLAttributes, ReactNode, TextareaHTMLAttributes } from "react";

interface BaseProps {
  label: string;
  hint?: string;
  error?: string;
  icon?: ReactNode;
}

type InputProps = BaseProps & InputHTMLAttributes<HTMLInputElement> & { multiline?: false };
type TextareaProps = BaseProps & TextareaHTMLAttributes<HTMLTextAreaElement> & { multiline: true };

export function FormField(props: InputProps | TextareaProps) {
  const { label, hint, error, icon, multiline, className = "", ...fieldProps } = props;
  const shared = `w-full rounded-xl border bg-[var(--surface-muted)] text-sm text-[var(--text-primary)] outline-none transition-all placeholder:text-[var(--text-tertiary)] focus:border-[var(--primary)] focus:ring-4 focus:ring-[var(--primary-soft)] ${error ? "border-[var(--danger)]" : "border-[var(--border)]"} ${icon ? "ps-11 pe-4" : "px-4"} ${className}`;

  return (
    <label className="block">
      <span className="mb-2 block text-sm font-semibold text-[var(--text-primary)]">{label}</span>
      <span className="relative block">
        {icon ? <span className="pointer-events-none absolute start-4 top-3.5 text-[var(--text-tertiary)]">{icon}</span> : null}
        {multiline ? (
          <textarea {...(fieldProps as TextareaHTMLAttributes<HTMLTextAreaElement>)} className={`${shared} min-h-28 resize-y py-3`} />
        ) : (
          <input {...(fieldProps as InputHTMLAttributes<HTMLInputElement>)} className={`${shared} h-12`} />
        )}
      </span>
      {error ? <span className="mt-1.5 block text-xs font-medium text-[var(--danger)]">{error}</span> : null}
      {!error && hint ? <span className="mt-1.5 block text-xs text-[var(--text-tertiary)]">{hint}</span> : null}
    </label>
  );
}
