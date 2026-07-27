export function SegmentedControl<T extends string>({ value, options, onChange }: { value: T; options: Array<{ value: T; label: string }>; onChange: (value: T) => void }) {
  return (
    <div className="inline-flex rounded-xl border border-[var(--border)] bg-[var(--surface-muted)] p-1">
      {options.map((option) => (
        <button
          type="button"
          key={option.value}
          onClick={() => onChange(option.value)}
          className={`rounded-lg px-3 py-2 text-xs font-bold transition-all ${value === option.value ? "bg-[var(--surface)] text-[var(--primary)] shadow-sm" : "text-[var(--text-tertiary)] hover:text-[var(--text-primary)]"}`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
