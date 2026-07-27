import { BookOpenCheck, Building2, FileText, Hash, Layers3 } from "lucide-react";
import type { ReactNode } from "react";

import { useI18n } from "../../lib/i18n";
import type { AssistantReference } from "../../lib/types";
import { Badge } from "../ui/Badge";
import { Modal } from "../ui/Modal";

export function ReferenceModal({
  reference,
  onClose,
}: {
  reference: AssistantReference | null;
  onClose: () => void;
}) {
  const { t } = useI18n();

  return (
    <Modal
      open={Boolean(reference)}
      onClose={onClose}
      title={t("approvedClinicalReference")}
      description={t("referenceMetadataDescription")}
      maxWidth="max-w-xl"
    >
      {reference ? (
        <div className="space-y-4">
          <div className="rounded-2xl bg-[linear-gradient(135deg,var(--primary-soft),var(--ai-soft))] p-5">
            <div className="flex items-start gap-4">
              <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-[var(--surface)] text-[var(--primary)] shadow-sm">
                <BookOpenCheck size={22} />
              </span>
              <div className="min-w-0">
                <div className="text-base font-extrabold leading-6 text-[var(--text-primary)]">
                  {reference.title || reference.source_id || t("clinicalReference")}
                </div>
                <div className="mt-2 flex flex-wrap gap-2">
                  {reference.citation_number != null ? <Badge tone="primary">[{reference.citation_number}]</Badge> : null}
                  {reference.source_id ? <Badge tone="neutral">{reference.source_id}</Badge> : null}
                </div>
              </div>
            </div>
          </div>

          <ReferenceRow icon={<Building2 size={17} />} label={t("organization")} value={reference.organization || "—"} />
          <ReferenceRow icon={<Layers3 size={17} />} label={t("section")} value={reference.section || "—"} />
          <ReferenceRow icon={<FileText size={17} />} label={t("page")} value={reference.page != null ? String(reference.page) : "—"} />
          <ReferenceRow icon={<Hash size={17} />} label={t("chunkReference")} value={reference.chunk_id || "—"} />

          {reference.score != null ? (
            <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface-muted)] p-4">
              <div className="flex items-center justify-between gap-4 text-xs font-bold text-[var(--text-secondary)]">
                <span>{t("retrievalRelevance")}</span>
                <span className="font-mono tabular-nums text-[var(--primary)]">{reference.score.toFixed(4)}</span>
              </div>
              <div className="mt-3 h-2 overflow-hidden rounded-full bg-[var(--border)]">
                <div
                  className="h-full rounded-full bg-[linear-gradient(90deg,var(--primary),var(--ai-accent))]"
                  style={{ width: `${Math.max(4, Math.min(100, reference.score * 100))}%` }}
                />
              </div>
            </div>
          ) : null}

          <p className="rounded-2xl bg-[var(--ai-soft)] px-4 py-3 text-xs leading-6 text-[var(--text-secondary)]">
            {t("referenceSafetyNote")}
          </p>
        </div>
      ) : null}
    </Modal>
  );
}

function ReferenceRow({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return (
    <div className="flex items-start gap-3 rounded-2xl border border-[var(--border)] px-4 py-3.5">
      <span className="mt-0.5 text-[var(--primary)]">{icon}</span>
      <div className="min-w-0">
        <div className="text-[0.68rem] font-bold uppercase tracking-[0.12em] text-[var(--text-tertiary)]">{label}</div>
        <div className="mt-1 break-words text-sm font-semibold leading-6 text-[var(--text-primary)]">{value}</div>
      </div>
    </div>
  );
}
