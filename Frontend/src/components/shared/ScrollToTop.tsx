import { AnimatePresence, motion } from "framer-motion";
import { ArrowUp } from "lucide-react";
import { useEffect, useState } from "react";

import { useI18n } from "../../lib/i18n";

export function ScrollToTop() {
  const [visible, setVisible] = useState(false);
  const { t } = useI18n();

  useEffect(() => {
    const onScroll = () => setVisible(window.scrollY > 420);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <AnimatePresence>
      {visible ? (
        <motion.button
          initial={{ opacity: 0, scale: 0.78, y: 12 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.78, y: 12 }}
          onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
          className="fixed bottom-5 end-5 z-40 inline-flex h-12 w-12 items-center justify-center rounded-2xl border border-white/15 bg-[linear-gradient(135deg,var(--primary),var(--ai-accent))] text-white shadow-[0_16px_40px_-14px_var(--primary)] transition-transform hover:-translate-y-1"
          aria-label={t("backToTop")}
          title={t("backToTop")}
        >
          <ArrowUp size={20} />
        </motion.button>
      ) : null}
    </AnimatePresence>
  );
}
