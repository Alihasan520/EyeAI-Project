import { motion } from "framer-motion";
import { BrainCircuit, Database, Sparkles } from "lucide-react";

import { useI18n } from "../../lib/i18n";

export function AssistantThinkingIndicator({ stage }: { stage: number }) {
  const { t } = useI18n();
  const stages = [
    { icon: Database, label: t("retrievingClinicalContext") },
    { icon: BrainCircuit, label: t("reviewingPatientEvidence") },
    { icon: Sparkles, label: t("draftingGroundedResponse") },
  ];
  const current = stages[Math.min(stage, stages.length - 1)];
  const Icon = current.icon;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="inline-flex items-center gap-3 rounded-2xl border border-[var(--border)] bg-[var(--surface-muted)] px-4 py-3 shadow-sm"
    >
      <span className="relative flex h-9 w-9 items-center justify-center">
        <motion.span
          className="absolute inset-0 rounded-full border-2 border-transparent border-t-[var(--primary)] border-e-[var(--ai-accent)]"
          animate={{ rotate: 360 }}
          transition={{ duration: 1.15, repeat: Infinity, ease: "linear" }}
        />
        <motion.span
          className="absolute inset-[5px] rounded-full bg-[linear-gradient(135deg,var(--primary-soft),var(--ai-soft))]"
          animate={{ scale: [0.92, 1.06, 0.92], opacity: [0.72, 1, 0.72] }}
          transition={{ duration: 1.7, repeat: Infinity, ease: "easeInOut" }}
        />
        <Icon size={15} className="relative text-[var(--primary)]" />
      </span>
      <div>
        <div className="text-xs font-extrabold text-[var(--text-primary)]">{t("clinicalCopilotThinking")}</div>
        <motion.div
          key={current.label}
          initial={{ opacity: 0, x: -4 }}
          animate={{ opacity: 1, x: 0 }}
          className="mt-0.5 text-[0.7rem] text-[var(--text-secondary)]"
        >
          {current.label}
        </motion.div>
      </div>
      <span className="ms-1 flex gap-1">
        {[0, 1, 2].map((index) => (
          <motion.span
            key={index}
            className="h-1.5 w-1.5 rounded-full bg-[var(--ai-accent)]"
            animate={{ y: [0, -4, 0], opacity: [0.35, 1, 0.35] }}
            transition={{ duration: 1, repeat: Infinity, delay: index * 0.14 }}
          />
        ))}
      </span>
    </motion.div>
  );
}
