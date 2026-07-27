import { motion } from "framer-motion";

interface EyeAILogoProps {
  compact?: boolean;
  className?: string;
  animated?: boolean;
}

export function EyeAILogo({
  compact = false,
  className = "",
  animated = false,
}: EyeAILogoProps) {
  return (
    <div className={`inline-flex items-center gap-3 ${className}`}>
      <motion.div
        className="relative shrink-0"
        animate={animated ? { scale: [1, 1.04, 1] } : undefined}
        transition={animated ? { duration: 2.4, repeat: Infinity, ease: "easeInOut" } : undefined}
      >
        <svg
          viewBox="0 0 96 96"
          aria-hidden="true"
          className="h-10 w-10 overflow-visible"
        >
          <defs>
            <linearGradient id="eyeai-logo-gradient" x1="12" y1="14" x2="84" y2="82">
              <stop stopColor="#2DD4BF" />
              <stop offset="1" stopColor="#7C83FF" />
            </linearGradient>
            <radialGradient id="eyeai-logo-glow" cx="50%" cy="50%" r="50%">
              <stop offset="0" stopColor="#E8FFFB" stopOpacity="0.95" />
              <stop offset="0.35" stopColor="#2DD4BF" stopOpacity="0.55" />
              <stop offset="1" stopColor="#2DD4BF" stopOpacity="0" />
            </radialGradient>
          </defs>
          <path
            d="M8.5 48c10.7-17.3 24-26 39.5-26s28.8 8.7 39.5 26C76.8 65.3 63.5 74 48 74S19.2 65.3 8.5 48Z"
            fill="none"
            stroke="url(#eyeai-logo-gradient)"
            strokeWidth="6"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <circle cx="48" cy="48" r="22" fill="url(#eyeai-logo-glow)" />
          <circle
            cx="48"
            cy="48"
            r="12"
            fill="none"
            stroke="url(#eyeai-logo-gradient)"
            strokeWidth="4"
          />
          <circle cx="48" cy="48" r="4.5" fill="#7C83FF" />
          <path
            d="M22 48h52"
            stroke="currentColor"
            strokeOpacity="0.35"
            strokeWidth="2.5"
            strokeLinecap="round"
          />
          {animated ? (
            <motion.path
              d="M26 32v32"
              stroke="#2DD4BF"
              strokeWidth="2"
              strokeLinecap="round"
              initial={{ x: 0, opacity: 0.2 }}
              animate={{ x: [0, 44, 0], opacity: [0.15, 0.8, 0.15] }}
              transition={{ duration: 2.7, repeat: Infinity, ease: "easeInOut" }}
            />
          ) : null}
        </svg>
      </motion.div>

      {!compact ? (
        <div className="min-w-0 leading-none">
          <div className="flex items-baseline gap-0.5 text-[1.35rem] font-extrabold tracking-[-0.04em] text-[var(--text-primary)]">
            <span>Eye</span>
            <span className="brand-gradient-text">AI</span>
          </div>
          <div className="mt-1 whitespace-nowrap text-[0.62rem] font-semibold uppercase tracking-[0.22em] text-[var(--text-tertiary)]">
            Clinical Intelligence
          </div>
        </div>
      ) : null}
    </div>
  );
}
