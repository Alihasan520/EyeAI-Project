import { motion } from "framer-motion";
import { ArrowLeft, Construction, Sparkles } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { useI18n } from "../lib/i18n";
import type { TranslationKey } from "../lib/translations";

export function PlaceholderPage({ titleKey }: { titleKey: TranslationKey }) {
  const { t, language } = useI18n();
  const navigate = useNavigate();

  return (
    <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} className="py-4">
      <Card className="relative overflow-hidden p-8 text-center sm:p-14">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_20%,var(--primary-soft),transparent_45%)] opacity-80" />
        <div className="relative mx-auto max-w-xl">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-3xl bg-[linear-gradient(135deg,var(--primary-soft),var(--ai-soft))] text-[var(--primary)]">
            <Construction size={28} />
          </div>
          <BadgeLine />
          <h2 className="mt-4 text-2xl font-extrabold tracking-[-0.03em] text-[var(--text-primary)]">{t(titleKey)}</h2>
          <p className="mx-auto mt-3 max-w-md text-sm leading-7 text-[var(--text-secondary)]">{t("comingSoon")}</p>
          <Button
            variant="secondary"
            className="mt-7"
            icon={<ArrowLeft size={17} className={language === "ar" ? "rotate-180" : ""} />}
            onClick={() => navigate("/")}
          >
            {t("dashboard")}
          </Button>
        </div>
      </Card>
    </motion.div>
  );
}

function BadgeLine() {
  return (
    <div className="mt-6 inline-flex items-center gap-2 rounded-full bg-[var(--ai-soft)] px-3 py-1.5 text-xs font-semibold text-[var(--ai-accent)]">
      <Sparkles size={14} />
      Frontend roadmap
    </div>
  );
}
