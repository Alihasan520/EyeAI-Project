import { useMutation, useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import {
  Activity,
  ArrowRight,
  Eye,
  LoaderCircle,
  LockKeyhole,
  Mail,
  ShieldCheck,
  Sparkles,
  WifiOff,
} from "lucide-react";
import { type FormEvent, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import { EyeAILogo } from "../components/brand/EyeAILogo";
import { WorkspaceSetupModal } from "../components/auth/WorkspaceSetupModal";
import { ConnectionSettingsModal } from "../components/shared/ConnectionSettingsModal";
import { LanguageSwitch } from "../components/shared/LanguageSwitch";
import { ThemeToggle } from "../components/shared/ThemeToggle";
import { Button } from "../components/ui/Button";
import { useAuthStore } from "../features/auth/auth-store";
import { useSettingsStore } from "../features/settings/settings-store";
import { useBackendHealth } from "../hooks/use-backend-health";
import { ApiError, getBootstrapStatus, login } from "../lib/api";
import { useI18n } from "../lib/i18n";
import { PREVIEW_MODE_ENABLED } from "../lib/runtime";

function RetinalVisual() {
  return (
    <div className="relative mx-auto aspect-square w-full max-w-[540px]">
      <div className="absolute inset-[9%] rounded-full bg-[radial-gradient(circle_at_50%_50%,rgba(45,212,191,0.23),rgba(124,131,255,0.08)_36%,transparent_68%)] blur-2xl" />
      <motion.div
        className="absolute inset-[14%] rounded-full border border-white/12"
        animate={{ rotate: 360 }}
        transition={{ duration: 26, repeat: Infinity, ease: "linear" }}
      >
        <span className="absolute start-1/2 top-0 h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-[#2dd4bf] shadow-[0_0_24px_6px_rgba(45,212,191,.45)]" />
        <span className="absolute bottom-[9%] end-[9%] h-2 w-2 rounded-full bg-[#7c83ff] shadow-[0_0_20px_5px_rgba(124,131,255,.45)]" />
      </motion.div>
      <motion.div
        className="absolute inset-[23%] rounded-full border border-white/10"
        animate={{ rotate: -360 }}
        transition={{ duration: 18, repeat: Infinity, ease: "linear" }}
      >
        <span className="absolute start-[8%] top-[25%] h-1.5 w-1.5 rounded-full bg-white/70" />
        <span className="absolute bottom-[14%] end-[20%] h-1.5 w-1.5 rounded-full bg-[#2dd4bf]" />
      </motion.div>

      <svg viewBox="0 0 600 600" className="absolute inset-0 h-full w-full" aria-hidden="true">
        <defs>
          <linearGradient id="login-eye-gradient" x1="90" y1="130" x2="510" y2="475">
            <stop stopColor="#2DD4BF" />
            <stop offset="1" stopColor="#7C83FF" />
          </linearGradient>
          <radialGradient id="login-eye-radial" cx="50%" cy="50%" r="50%">
            <stop offset="0" stopColor="#F0FFFD" stopOpacity=".95" />
            <stop offset=".28" stopColor="#2DD4BF" stopOpacity=".55" />
            <stop offset="1" stopColor="#2DD4BF" stopOpacity="0" />
          </radialGradient>
        </defs>
        <path
          d="M76 300c61-94 136-141 224-141S463 206 524 300C463 394 388 441 300 441S137 394 76 300Z"
          fill="rgba(3,12,24,.38)"
          stroke="url(#login-eye-gradient)"
          strokeWidth="8"
          strokeLinecap="round"
        />
        <circle cx="300" cy="300" r="126" fill="url(#login-eye-radial)" />
        <circle cx="300" cy="300" r="78" fill="rgba(9,27,43,.8)" stroke="url(#login-eye-gradient)" strokeWidth="5" />
        <circle cx="300" cy="300" r="31" fill="#7C83FF" fillOpacity=".92" />
        <circle cx="300" cy="300" r="12" fill="#EFFFFC" />
        <path d="M128 300h344" stroke="rgba(255,255,255,.35)" strokeWidth="2" />
        <path d="M300 214v172" stroke="rgba(255,255,255,.18)" strokeWidth="2" />
      </svg>

      <motion.div
        className="absolute inset-y-[27%] w-[2px] rounded-full bg-[linear-gradient(180deg,transparent,#2dd4bf,white,#7c83ff,transparent)] shadow-[0_0_22px_rgba(45,212,191,.65)]"
        animate={{ left: ["25%", "75%", "25%"] }}
        transition={{ duration: 4.2, repeat: Infinity, ease: "easeInOut" }}
      />

      <div className="absolute bottom-[3%] start-1/2 flex -translate-x-1/2 items-center gap-2 rounded-full border border-white/10 bg-[#07111f]/70 px-4 py-2 text-xs font-semibold text-white/75 backdrop-blur-xl">
        <Activity size={14} className="text-[#2dd4bf]" />
        RETFound · Explainability · RAG
      </div>
    </div>
  );
}

export function LoginPage() {
  const user = useAuthStore((state) => state.user);
  const startPreview = useAuthStore((state) => state.startPreview);
  const backendState = useSettingsStore((state) => state.backendState);
  const { t, language } = useI18n();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [connectionOpen, setConnectionOpen] = useState(false);
  const [setupOpen, setSetupOpen] = useState(false);

  useBackendHealth(true);

  const bootstrapStatus = useQuery({
    queryKey: ["bootstrap-status", backendState],
    queryFn: getBootstrapStatus,
    enabled: backendState === "online",
    retry: false,
  });

  const mutation = useMutation({
    mutationFn: () => login(email, password),
    onSuccess: () => navigate("/", { replace: true }),
  });

  if (user) {
    return <Navigate to="/" replace />;
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    mutation.mutate();
  }

  const errorText = mutation.error
    ? mutation.error instanceof ApiError && mutation.error.status === 401
      ? t("invalidCredentials")
      : mutation.error instanceof Error
        ? mutation.error.message
        : t("requestFailed")
    : "";

  return (
    <div className="min-h-screen overflow-hidden bg-[var(--page-bg)] text-[var(--text-primary)]">
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(circle_at_10%_15%,rgba(45,212,191,.10),transparent_28%),radial-gradient(circle_at_88%_80%,rgba(124,131,255,.12),transparent_32%)]" />
      <div className="relative grid min-h-screen lg:grid-cols-[minmax(0,0.88fr)_minmax(540px,1.12fr)]">
        <main className="flex min-h-screen items-center justify-center px-5 py-8 sm:px-10 lg:px-14 xl:px-20">
          <motion.div
            className="w-full max-w-[480px]"
            initial={{ opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.45 }}
          >
            <div className="flex items-center justify-between gap-4">
              <EyeAILogo />
              <div className="flex items-center gap-2">
                <LanguageSwitch />
                <ThemeToggle />
              </div>
            </div>

            <div className="mt-12 sm:mt-16">
              <div className="inline-flex items-center gap-2 rounded-full bg-[var(--ai-soft)] px-3 py-1.5 text-xs font-semibold text-[var(--ai-accent)]">
                <Sparkles size={14} />
                {t("brandTagline")}
              </div>
              <h1 className="mt-5 text-3xl font-extrabold tracking-[-0.04em] text-[var(--text-primary)] sm:text-4xl">
                {t("loginTitle")}
              </h1>
              <p className="mt-3 max-w-md text-sm leading-7 text-[var(--text-secondary)] sm:text-base">
                {t("loginSubtitle")}
              </p>
            </div>

            <button
              type="button"
              onClick={() => setConnectionOpen(true)}
              className={`mt-7 flex w-full items-center justify-between rounded-2xl border px-4 py-3 text-start transition-all ${backendState === "online" ? "border-[var(--success)]/20 bg-[var(--success-soft)]" : backendState === "warming" ? "border-[var(--warning)]/20 bg-[var(--warning-soft)]" : "border-[var(--danger)]/20 bg-[var(--danger-soft)]"}`}
            >
              <span className="flex items-center gap-3">
                <span className={`flex h-9 w-9 items-center justify-center rounded-xl ${backendState === "online" ? "text-[var(--success)]" : backendState === "warming" ? "text-[var(--warning)]" : "text-[var(--danger)]"}`}>
                  {backendState === "warming" ? <LoaderCircle size={18} className="animate-spin" /> : backendState === "online" ? <Activity size={18} /> : <WifiOff size={18} />}
                </span>
                <span>
                  <span className="block text-xs font-bold text-[var(--text-primary)]">
                    {backendState === "online" ? t("backendOnline") : backendState === "warming" ? t("backendWarming") : t("backendOffline")}
                  </span>
                  <span className="mt-0.5 block text-[0.68rem] text-[var(--text-tertiary)]">{t("openSettings")}</span>
                </span>
              </span>
              <ArrowRight size={17} className={language === "ar" ? "rotate-180" : ""} />
            </button>

            {bootstrapStatus.data?.available ? (
              <motion.button
                type="button"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                onClick={() => setSetupOpen(true)}
                className="mt-6 flex w-full items-center justify-between rounded-2xl border border-[var(--primary)]/25 bg-[linear-gradient(135deg,var(--primary-soft),var(--ai-soft))] px-4 py-4 text-start transition-all hover:-translate-y-0.5 hover:border-[var(--primary)]/45"
              >
                <span className="flex items-center gap-3">
                  <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[linear-gradient(135deg,var(--primary),var(--ai-accent))] text-white">
                    <ShieldCheck size={19} />
                  </span>
                  <span>
                    <span className="block text-sm font-extrabold text-[var(--text-primary)]">{t("initializeWorkspace")}</span>
                    <span className="mt-0.5 block text-xs text-[var(--text-secondary)]">{t("createFirstAdministrator")}</span>
                  </span>
                </span>
                <ArrowRight size={18} className={language === "ar" ? "rotate-180" : ""} />
              </motion.button>
            ) : null}

            <form className="mt-7 space-y-4" onSubmit={handleSubmit}>
              <label className="block">
                <span className="mb-2 block text-sm font-semibold text-[var(--text-primary)]">{t("email")}</span>
                <span className="relative block">
                  <Mail size={18} className="pointer-events-none absolute start-4 top-1/2 -translate-y-1/2 text-[var(--text-tertiary)]" />
                  <input
                    type="email"
                    required
                    autoComplete="email"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    className="h-12 w-full rounded-xl border border-[var(--border)] bg-[var(--surface)] ps-11 pe-4 text-sm outline-none transition-all placeholder:text-[var(--text-tertiary)] focus:border-[var(--primary)] focus:ring-4 focus:ring-[var(--primary-soft)]"
                    placeholder="doctor@eyeai.local"
                  />
                </span>
              </label>

              <label className="block">
                <span className="mb-2 block text-sm font-semibold text-[var(--text-primary)]">{t("password")}</span>
                <span className="relative block">
                  <LockKeyhole size={18} className="pointer-events-none absolute start-4 top-1/2 -translate-y-1/2 text-[var(--text-tertiary)]" />
                  <input
                    type="password"
                    required
                    autoComplete="current-password"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    className="h-12 w-full rounded-xl border border-[var(--border)] bg-[var(--surface)] ps-11 pe-4 text-sm outline-none transition-all placeholder:text-[var(--text-tertiary)] focus:border-[var(--primary)] focus:ring-4 focus:ring-[var(--primary-soft)]"
                    placeholder="••••••••••••"
                  />
                </span>
              </label>

              <AnimatePresence>
                {errorText ? (
                  <motion.div
                    initial={{ opacity: 0, y: -5 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -5 }}
                    className="rounded-xl bg-[var(--danger-soft)] px-4 py-3 text-sm font-medium text-[var(--danger)]"
                  >
                    {errorText}
                  </motion.div>
                ) : null}
              </AnimatePresence>

              <Button type="submit" size="lg" fullWidth disabled={mutation.isPending || !email || !password}>
                {mutation.isPending ? <LoaderCircle size={18} className="animate-spin" /> : <ShieldCheck size={18} />}
                {mutation.isPending ? t("signingIn") : t("signIn")}
              </Button>
            </form>

            {PREVIEW_MODE_ENABLED ? (
              <div className="mt-5">
                <Button
                  type="button"
                  variant="secondary"
                  fullWidth
                  onClick={() => {
                    startPreview();
                    navigate("/", { replace: true });
                  }}
                  icon={<Eye size={18} />}
                >
                  {t("previewWorkspace")}
                </Button>
                <p className="mt-2 text-center text-xs leading-5 text-[var(--text-tertiary)]">{t("previewHint")}</p>
              </div>
            ) : null}

            <div className="mt-10 flex items-center gap-2 text-xs text-[var(--text-tertiary)]">
              <ShieldCheck size={15} className="text-[var(--primary)]" />
              AI-assisted screening prototype · Clinical review required
            </div>
          </motion.div>
        </main>

        <aside className="relative hidden min-h-screen overflow-hidden border-s border-white/8 bg-[#07111f] p-8 lg:flex lg:items-center xl:p-14">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_25%_15%,rgba(45,212,191,.16),transparent_28%),radial-gradient(circle_at_78%_75%,rgba(124,131,255,.2),transparent_32%)]" />
          <div className="absolute inset-0 opacity-[0.05] [background-image:linear-gradient(rgba(255,255,255,.6)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,.6)_1px,transparent_1px)] [background-size:42px_42px]" />
          <div className="relative z-10 w-full">
            <RetinalVisual />
            <div className="mx-auto mt-5 max-w-xl text-center">
              <h2 className="text-2xl font-bold tracking-[-0.03em] text-white xl:text-3xl">
                AI-assisted retinal screening,
                <br /> explainability, and longitudinal care.
              </h2>
              <p className="mx-auto mt-4 max-w-lg text-sm leading-7 text-white/58">
                A focused clinical workspace that connects RETFound inference, heatmap interpretation, approved references, and patient history.
              </p>
            </div>
          </div>
        </aside>
      </div>

      <ConnectionSettingsModal open={connectionOpen} onClose={() => setConnectionOpen(false)} />
      <WorkspaceSetupModal
        open={setupOpen}
        onClose={() => setSetupOpen(false)}
        onReady={() => navigate("/", { replace: true })}
      />
    </div>
  );
}
