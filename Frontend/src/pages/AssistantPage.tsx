import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  ArrowUp,
  Bot,
  BookOpenCheck,
  BrainCircuit,
  CheckCircle2,
  ChevronDown,
  CircleAlert,
  Eye,
  FileText,
  History,
  LoaderCircle,
  MessageSquarePlus,
  ShieldCheck,
  Sparkles,
  UserRound,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useSearchParams } from "react-router-dom";

import { AssistantThinkingIndicator } from "../components/assistant/AssistantThinkingIndicator";
import { ReferenceModal } from "../components/assistant/ReferenceModal";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { PageHeader } from "../components/ui/PageHeader";
import { SegmentedControl } from "../components/ui/SegmentedControl";
import { useAuthStore } from "../features/auth/auth-store";
import {
  createAssistantConversation,
  listAssistantConversations,
  listAssistantMessages,
  listPatients,
  listVisits,
  sendAssistantMessage,
} from "../lib/api";
import { formatDate } from "../lib/format";
import { useI18n } from "../lib/i18n";
import type {
  AssistantConversation,
  AssistantMessage,
  AssistantReference,
  AssistantResult,
  EyeSide,
} from "../lib/types";


export function AssistantPage() {
  const { t, language } = useI18n();
  const previewMode = useAuthStore((state) => state.previewMode);
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const scrollRef = useRef<HTMLDivElement>(null);
  const stageTimerRef = useRef<number | null>(null);

  const [patientRef, setPatientRef] = useState(searchParams.get("patient") || "");
  const [eye, setEye] = useState<EyeSide>((searchParams.get("eye") as EyeSide) || "right");
  const [visitRef, setVisitRef] = useState(searchParams.get("visit") || "");
  const [conversationRef, setConversationRef] = useState(searchParams.get("conversation") || "");
  const [question, setQuestion] = useState("");
  const [thinkingStage, setThinkingStage] = useState(0);
  const [lastResult, setLastResult] = useState<AssistantResult | null>(null);
  const [selectedReference, setSelectedReference] = useState<AssistantReference | null>(null);
  const [pendingQuestion, setPendingQuestion] = useState("");

  const suggestedPrompts = useMemo(
    () => [
      t("promptSummarizeVisit"),
      t("promptExplainHeatmap"),
      t("promptReferences"),
      t("promptCompareVisit"),
      t("promptDraftNote"),
    ],
    [t],
  );

  const patientsQuery = useQuery({
    queryKey: ["patients", "assistant"],
    queryFn: () => listPatients(),
    enabled: !previewMode,
  });
  const visitsQuery = useQuery({
    queryKey: ["visits", "assistant"],
    queryFn: () => listVisits(),
    enabled: !previewMode,
  });
  const conversationsQuery = useQuery({
    queryKey: ["assistant-conversations", patientRef],
    queryFn: () => listAssistantConversations(patientRef),
    enabled: !previewMode && Boolean(patientRef),
  });
  const messagesQuery = useQuery({
    queryKey: ["assistant-messages", conversationRef],
    queryFn: () => listAssistantMessages(conversationRef),
    enabled: !previewMode && Boolean(conversationRef),
  });

  const patients = patientsQuery.data || [];
  const visits = visitsQuery.data || [];
  const patientVisits = useMemo(
    () => visits.filter((item) => item.patient_display_id === patientRef && item.visit.eye === eye),
    [eye, patientRef, visits],
  );
  const conversations = conversationsQuery.data || [];
  const activeConversation = conversations.find((item) => item.display_id === conversationRef);
  const messages = messagesQuery.data || [];

  useEffect(() => {
    if (!visitRef) return;
    const visit = visits.find((item) => item.visit.display_id === visitRef);
    if (!visit) return;
    setPatientRef(visit.patient_display_id);
    setEye(visit.visit.eye);
  }, [visitRef, visits]);

  useEffect(() => {
    if (conversationRef || !conversations.length) return;
    const selectedVisit = visits.find((item) => item.visit.display_id === visitRef);
    const preferred = visitRef
      ? conversations.find((item) => item.visit_id === selectedVisit?.visit.id)
      : conversations[0];
    if (preferred) setConversationRef(preferred.display_id);
  }, [conversationRef, conversations, visitRef]);

  useEffect(() => {
    const params: Record<string, string> = {};
    if (patientRef) params.patient = patientRef;
    if (visitRef) params.visit = visitRef;
    if (eye) params.eye = eye;
    if (conversationRef) params.conversation = conversationRef;
    setSearchParams(params, { replace: true });
  }, [conversationRef, eye, patientRef, setSearchParams, visitRef]);

  useEffect(() => {
    requestAnimationFrame(() => {
      scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
    });
  }, [messages, lastResult]);

  useEffect(() => () => {
    if (stageTimerRef.current) window.clearInterval(stageTimerRef.current);
  }, []);

  const createConversationMutation = useMutation({
    mutationFn: () => {
      if (!patientRef) throw new Error(t("selectPatientFirst"));
      return createAssistantConversation(patientRef, {
        eye,
        visit_id: visitRef || null,
        title: visitRef ? `${t("visitReview")} · ${visitRef}` : t("clinicalReviewConversation"),
      });
    },
    onSuccess: (conversation) => {
      void queryClient.invalidateQueries({ queryKey: ["assistant-conversations", patientRef] });
      setConversationRef(conversation.display_id);
      setLastResult(null);
    },
  });

  const sendMutation = useMutation({
    mutationFn: (content: string) => {
      if (!conversationRef) throw new Error(t("createConversationFirst"));
      return sendAssistantMessage(conversationRef, content);
    },
    onMutate: (content) => {
      setPendingQuestion(content);
      setThinkingStage(0);
      if (stageTimerRef.current) window.clearInterval(stageTimerRef.current);
      stageTimerRef.current = window.setInterval(() => {
        setThinkingStage((current) => Math.min(current + 1, 2));
      }, 1700);
    },
    onSuccess: (turn) => {
      if (stageTimerRef.current) window.clearInterval(stageTimerRef.current);
      setLastResult(turn.result);
      setQuestion("");
      setPendingQuestion("");
      void queryClient.invalidateQueries({ queryKey: ["assistant-messages", conversationRef] });
    },
    onSettled: () => {
      if (stageTimerRef.current) window.clearInterval(stageTimerRef.current);
      setPendingQuestion("");
    },
  });

  const submitQuestion = (content = question) => {
    const cleaned = content.trim();
    if (!cleaned || sendMutation.isPending) return;
    sendMutation.mutate(cleaned);
  };

  if (previewMode) {
    return (
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
        <PageHeader
          eyebrow="EyeAI Clinical Intelligence"
          title={t("clinicalCopilot")}
          description={t("clinicalCopilotDescription")}
        />
        <EmptyState icon={<Bot size={26} />} title={t("liveBackendRequired")} description={t("assistantPreviewDisabled")} />
      </motion.div>
    );
  }

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
      <PageHeader
        eyebrow="EyeAI Clinical Intelligence"
        title={t("clinicalCopilot")}
        description={t("clinicalCopilotDescription")}
        actions={
          <div className="flex flex-wrap gap-2">
            <Badge tone={activeConversation?.rag_enabled ? "success" : "neutral"} dot>
              {activeConversation?.rag_enabled ? t("ragGrounded") : t("ragNotActive")}
            </Badge>
            <Button
              size="sm"
              variant="secondary"
              icon={<MessageSquarePlus size={16} />}
              onClick={() => createConversationMutation.mutate()}
              disabled={!patientRef || createConversationMutation.isPending}
            >
              {t("newConversation")}
            </Button>
          </div>
        }
      />

      <div className="grid min-h-[760px] gap-4 xl:grid-cols-[235px_minmax(0,1fr)] 2xl:grid-cols-[235px_minmax(680px,1fr)_285px]">
        <Card className="h-fit overflow-hidden xl:sticky xl:top-24">
          <div className="border-b border-[var(--border)] bg-[linear-gradient(135deg,var(--primary-soft),var(--ai-soft))] p-4">
            <div className="flex items-center gap-3">
              <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-[var(--surface)] text-[var(--primary)] shadow-sm">
                <UserRound size={19} />
              </span>
              <div>
                <div className="text-sm font-extrabold text-[var(--text-primary)]">{t("patientContext")}</div>
                <div className="text-xs text-[var(--text-secondary)]">{t("patientContextHint")}</div>
              </div>
            </div>
          </div>
          <div className="space-y-4 p-4">
            <SelectBlock label={t("patient")}>
              <select
                className="analysis-select"
                value={patientRef}
                onChange={(event) => {
                  setPatientRef(event.target.value);
                  setVisitRef("");
                  setConversationRef("");
                  setLastResult(null);
                }}
              >
                <option value="">{t("selectPatient")}</option>
                {patients.map((patient) => (
                  <option key={patient.id} value={patient.display_id}>
                    {patient.first_name} {patient.last_name} · {patient.display_id}
                  </option>
                ))}
              </select>
            </SelectBlock>

            <div>
              <div className="mb-2 text-sm font-semibold text-[var(--text-primary)]">{t("selectedEye")}</div>
              <SegmentedControl
                value={eye}
                options={[
                  { value: "right", label: t("rightEye") },
                  { value: "left", label: t("leftEye") },
                ]}
                onChange={(value) => {
                  setEye(value);
                  setVisitRef("");
                  setConversationRef("");
                }}
              />
            </div>

            <SelectBlock label={t("visit") }>
              <select
                className="analysis-select"
                value={visitRef}
                onChange={(event) => {
                  setVisitRef(event.target.value);
                  setConversationRef("");
                }}
                disabled={!patientRef}
              >
                <option value="">{t("allPatientContext")}</option>
                {patientVisits.map((item) => (
                  <option key={item.visit.id} value={item.visit.display_id}>
                    {item.visit.display_id} · {formatDate(item.visit.visit_date, language)}
                  </option>
                ))}
              </select>
            </SelectBlock>

            <div className="border-t border-[var(--border)] pt-4">
              <div className="mb-2 flex items-center gap-2 text-xs font-extrabold text-[var(--text-primary)]">
                <History size={15} className="text-[var(--primary)]" />
                {t("conversations")}
              </div>
              <div className="max-h-52 space-y-2 overflow-y-auto pe-1">
                {conversations.length ? conversations.map((conversation) => (
                  <button
                    key={conversation.id}
                    type="button"
                    onClick={() => {
                      setConversationRef(conversation.display_id);
                      if (conversation.visit_id) {
                        const boundVisit = visits.find((item) => item.visit.id === conversation.visit_id);
                        if (boundVisit) setVisitRef(boundVisit.visit.display_id);
                      }
                      setEye(conversation.eye);
                      setLastResult(null);
                    }}
                    className={`w-full rounded-xl border px-3 py-2.5 text-start transition-all ${conversation.display_id === conversationRef ? "border-[var(--primary)] bg-[var(--primary-soft)]" : "border-[var(--border)] hover:bg-[var(--surface-hover)]"}`}
                  >
                    <div className="truncate text-xs font-bold text-[var(--text-primary)]">{conversation.title || conversation.display_id}</div>
                    <div className="mt-1 flex items-center gap-2 text-[0.65rem] text-[var(--text-tertiary)]">
                      <Eye size={12} /> {conversation.eye === "right" ? t("rightEye") : t("leftEye")}
                      <span>·</span>
                      <span>{formatDate(conversation.updated_at, language)}</span>
                    </div>
                  </button>
                )) : (
                  <div className="rounded-xl border border-dashed border-[var(--border)] px-3 py-4 text-center text-xs text-[var(--text-tertiary)]">
                    {patientRef ? t("noConversationsYet") : t("selectPatientFirst")}
                  </div>
                )}
              </div>
            </div>
          </div>
        </Card>

        <Card className="flex min-h-[760px] flex-col overflow-hidden">
          <div className="flex items-center justify-between gap-3 border-b border-[var(--border)] px-5 py-4">
            <div className="flex items-center gap-3">
              <span className="relative flex h-10 w-10 items-center justify-center rounded-2xl bg-[linear-gradient(135deg,var(--primary),var(--ai-accent))] text-white">
                <Bot size={19} />
                <span className="absolute -end-1 -top-1 h-3 w-3 rounded-full border-2 border-[var(--surface)] bg-[var(--success)]" />
              </span>
              <div>
                <div className="font-extrabold text-[var(--text-primary)]">{t("eyeaiClinicalCopilot")}</div>
                <div className="text-xs text-[var(--text-secondary)]">
                  {activeConversation ? `${activeConversation.display_id} · ${activeConversation.model_name}` : t("selectOrCreateConversation")}
                </div>
              </div>
            </div>
            {activeConversation ? <Badge tone="neutral">{activeConversation.eye === "right" ? t("rightEye") : t("leftEye")}</Badge> : null}
          </div>

          <div ref={scrollRef} className="flex-1 space-y-5 overflow-y-auto bg-[color-mix(in_srgb,var(--surface-muted)_45%,transparent)] p-4 sm:p-6 lg:p-7">
            {!conversationRef ? (
              <div className="flex min-h-[430px] items-center justify-center">
                <EmptyState
                  icon={<BrainCircuit size={27} />}
                  title={t("startClinicalConversation")}
                  description={t("startClinicalConversationDescription")}
                  action={patientRef ? (
                    <Button icon={<MessageSquarePlus size={17} />} onClick={() => createConversationMutation.mutate()}>
                      {t("createConversation")}
                    </Button>
                  ) : undefined}
                />
              </div>
            ) : !messages.length && !sendMutation.isPending ? (
              <div className="py-8">
                <div className="mx-auto max-w-xl text-center">
                  <span className="mx-auto flex h-16 w-16 items-center justify-center rounded-3xl bg-[linear-gradient(135deg,var(--primary-soft),var(--ai-soft))] text-[var(--primary)]">
                    <Sparkles size={28} />
                  </span>
                  <h3 className="mt-5 text-xl font-extrabold text-[var(--text-primary)]">{t("askAboutCurrentCase")}</h3>
                  <p className="mx-auto mt-2 max-w-lg text-sm leading-6 text-[var(--text-secondary)]">{t("askAboutCurrentCaseDescription")}</p>
                </div>
                <div className="mx-auto mt-7 grid max-w-2xl gap-2 sm:grid-cols-2">
                  {suggestedPrompts.map((prompt, index) => (
                    <button
                      key={prompt}
                      type="button"
                      onClick={() => submitQuestion(prompt)}
                      className="group flex items-start gap-3 rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-3.5 text-start transition-all hover:-translate-y-0.5 hover:border-[var(--primary)] hover:shadow-[var(--shadow-card)]"
                    >
                      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-[var(--primary-soft)] text-[var(--primary)]">
                        {index === 1 ? <Eye size={15} /> : index === 2 ? <BookOpenCheck size={15} /> : index === 4 ? <FileText size={15} /> : <Sparkles size={15} />}
                      </span>
                      <span className="text-xs font-semibold leading-5 text-[var(--text-secondary)] group-hover:text-[var(--text-primary)]">{prompt}</span>
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <>
                {messages.map((message) => (
                  <MessageBubble
                    key={message.id}
                    message={message}
                    onReference={setSelectedReference}
                  />
                ))}
                {sendMutation.isPending && pendingQuestion ? (
                  <div className="flex justify-end">
                    <div className="max-w-[82%] rounded-[22px_22px_6px_22px] bg-[linear-gradient(135deg,var(--primary),var(--ai-accent))] px-4 py-3 text-sm leading-7 text-white opacity-90">
                      {pendingQuestion}
                    </div>
                  </div>
                ) : null}
                {sendMutation.isPending ? <AssistantThinkingIndicator stage={thinkingStage} /> : null}
              </>
            )}
          </div>

          <div className="border-t border-[var(--border)] bg-[var(--surface)] p-4 sm:p-5">
            <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface-muted)] p-2 transition-all focus-within:border-[var(--primary)] focus-within:ring-4 focus-within:ring-[var(--primary-soft)]">
              <textarea
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    submitQuestion();
                  }
                }}
                disabled={!conversationRef || sendMutation.isPending}
                rows={2}
                placeholder={conversationRef ? t("askClinicalQuestion") : t("createConversationFirst")}
                dir="auto"
                className="clinical-message-text max-h-44 min-h-[72px] w-full resize-none bg-transparent px-3 py-2.5 text-[0.95rem] leading-7 text-[var(--text-primary)] outline-none placeholder:text-[var(--text-tertiary)] disabled:cursor-not-allowed"
              />
              <div className="flex items-center justify-between gap-3 px-2 pb-1">
                <div className="flex items-center gap-2 text-[0.65rem] text-[var(--text-tertiary)]">
                  <ShieldCheck size={13} className="text-[var(--primary)]" />
                  {t("groundedAssistantDisclaimer")}
                </div>
                <button
                  type="button"
                  onClick={() => submitQuestion()}
                  disabled={!question.trim() || !conversationRef || sendMutation.isPending}
                  className="flex h-10 w-10 items-center justify-center rounded-xl bg-[linear-gradient(135deg,var(--primary),var(--ai-accent))] text-white shadow-lg transition-all hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
                  aria-label={t("sendMessage")}
                >
                  {sendMutation.isPending ? <LoaderCircle size={18} className="animate-spin" /> : <ArrowUp size={18} />}
                </button>
              </div>
            </div>
            {sendMutation.error ? (
              <div className="mt-2 rounded-xl bg-[var(--danger-soft)] px-3 py-2 text-xs font-semibold text-[var(--danger)]">
                {sendMutation.error instanceof Error ? sendMutation.error.message : t("requestFailed")}
              </div>
            ) : null}
          </div>
        </Card>

        <div className="space-y-5 xl:col-span-2 2xl:col-span-1 2xl:sticky 2xl:top-24 2xl:h-fit">
          <ClinicalEvidencePanel
            result={lastResult || extractLatestResult(messages)}
            onReference={setSelectedReference}
          />
          <Card className="p-4">
            <div className="flex items-center gap-2 text-sm font-extrabold text-[var(--text-primary)]">
              <ShieldCheck size={17} className="text-[var(--primary)]" />
              {t("clinicalSafetyBoundary")}
            </div>
            <p className="mt-3 text-xs leading-6 text-[var(--text-secondary)]">{t("clinicalSafetyBoundaryDescription")}</p>
          </Card>
        </div>
      </div>

      <ReferenceModal reference={selectedReference} onClose={() => setSelectedReference(null)} />
    </motion.div>
  );
}

function MessageBubble({ message, onReference }: { message: AssistantMessage; onReference: (reference: AssistantReference) => void }) {
  const { t } = useI18n();
  const isUser = message.role === "user";
  const structured = message.structured as AssistantResult | null;
  const references = message.references || structured?.references || [];

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className={`flex ${isUser ? "justify-end" : "justify-start"}`}
    >
      <div className={`max-w-[96%] sm:max-w-[90%] lg:max-w-[86%] ${isUser ? "rounded-[22px_22px_6px_22px] bg-[linear-gradient(135deg,var(--primary),var(--ai-accent))] px-4 py-3 text-white" : "rounded-[22px_22px_22px_6px] border border-[var(--border)] bg-[var(--surface)] p-4 sm:p-5 shadow-sm"}`}>
        {!isUser ? (
          <div className="mb-3 flex items-center gap-2 text-[0.7rem] font-extrabold text-[var(--primary)]">
            <Bot size={14} /> {t("eyeaiClinicalCopilot")}
          </div>
        ) : null}
        <p dir="auto" className={`clinical-message-text whitespace-pre-wrap text-[0.95rem] leading-8 ${isUser ? "text-white" : "text-[var(--text-primary)]"}`}>
          {structured?.answer || message.content}
        </p>
        {!isUser && references.length ? (
          <div className="mt-4 flex flex-wrap gap-2 border-t border-[var(--border)] pt-3">
            {references.map((reference, index) => (
              <button
                type="button"
                key={`${reference.source_id || index}-${reference.page || index}`}
                onClick={() => onReference(reference)}
                className="inline-flex items-center gap-1.5 rounded-full border border-[var(--border)] bg-[var(--surface-muted)] px-2.5 py-1.5 text-[0.68rem] font-bold text-[var(--text-secondary)] transition-colors hover:border-[var(--primary)] hover:text-[var(--primary)]"
              >
                <BookOpenCheck size={13} />
                [{reference.citation_number || index + 1}] {reference.source_id || t("source")}
              </button>
            ))}
          </div>
        ) : null}
      </div>
    </motion.div>
  );
}

function ClinicalEvidencePanel({ result, onReference }: { result: AssistantResult | null; onReference: (reference: AssistantReference) => void }) {
  const { t } = useI18n();
  const evidence = stringArray(result?.patient_evidence);
  const interpretation = stringArray(result?.clinical_interpretation);
  const limitations = stringArray(result?.limitations);
  const references = (result?.references || []) as AssistantReference[];

  return (
    <Card className="overflow-hidden">
      <div className="border-b border-[var(--border)] bg-[linear-gradient(135deg,var(--primary-soft),var(--ai-soft))] p-4">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-[var(--surface)] text-[var(--ai-accent)] shadow-sm">
            <BrainCircuit size={19} />
          </span>
          <div>
            <div className="text-sm font-extrabold text-[var(--text-primary)]">{t("evidenceWorkspace")}</div>
            <div className="text-xs text-[var(--text-secondary)]">{t("evidenceWorkspaceHint")}</div>
          </div>
        </div>
      </div>
      {!result ? (
        <div className="p-5 text-center text-xs leading-6 text-[var(--text-tertiary)]">{t("evidenceAppearsAfterResponse")}</div>
      ) : (
        <div className="space-y-4 p-4">
          <EvidenceSection icon={<CheckCircle2 size={16} />} title={t("patientEvidence")} items={evidence} tone="primary" />
          <EvidenceSection icon={<Sparkles size={16} />} title={t("clinicalInterpretation")} items={interpretation} tone="ai" />
          <EvidenceSection icon={<CircleAlert size={16} />} title={t("limitations")} items={limitations} tone="warning" />
          {result.suggested_review ? (
            <div className="rounded-2xl bg-[var(--success-soft)] p-4">
              <div className="text-xs font-extrabold text-[var(--success)]">{t("suggestedReview")}</div>
              <p className="mt-2 text-xs leading-6 text-[var(--text-secondary)]">{result.suggested_review}</p>
            </div>
          ) : null}
          {references.length ? (
            <div>
              <div className="mb-2 text-xs font-extrabold text-[var(--text-primary)]">{t("sources")}</div>
              <div className="space-y-2">
                {references.map((reference, index) => (
                  <button
                    key={`${reference.source_id || index}-${reference.page || index}`}
                    type="button"
                    onClick={() => onReference(reference)}
                    className="flex w-full items-start gap-3 rounded-xl border border-[var(--border)] p-3 text-start transition-all hover:border-[var(--primary)] hover:bg-[var(--surface-hover)]"
                  >
                    <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-[var(--primary-soft)] text-xs font-extrabold text-[var(--primary)]">{reference.citation_number || index + 1}</span>
                    <span className="min-w-0">
                      <span className="block truncate text-xs font-bold text-[var(--text-primary)]">{reference.title || reference.source_id}</span>
                      <span className="mt-1 block text-[0.65rem] text-[var(--text-tertiary)]">{reference.section || t("clinicalSection")} · {t("page")} {reference.page ?? "—"}</span>
                    </span>
                  </button>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      )}
    </Card>
  );
}

function EvidenceSection({ icon, title, items, tone }: { icon: ReactNode; title: string; items: string[]; tone: "primary" | "ai" | "warning" }) {
  if (!items.length) return null;
  const styles = {
    primary: "bg-[var(--primary-soft)] text-[var(--primary)]",
    ai: "bg-[var(--ai-soft)] text-[var(--ai-accent)]",
    warning: "bg-[var(--warning-soft)] text-[var(--warning)]",
  };
  return (
    <div>
      <div className="mb-2 flex items-center gap-2 text-xs font-extrabold text-[var(--text-primary)]">{icon}{title}</div>
      <div className="space-y-2">
        {items.map((item, index) => (
          <div key={`${item}-${index}`} className="flex items-start gap-2 text-xs leading-5 text-[var(--text-secondary)]">
            <span className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${styles[tone]}`} />
            <span>{item}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function SelectBlock({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-2 block text-sm font-semibold text-[var(--text-primary)]">{label}</span>
      <span className="relative block">
        {children}
        <ChevronDown size={16} className="pointer-events-none absolute end-4 top-1/2 -translate-y-1/2 text-[var(--text-tertiary)]" />
      </span>
    </label>
  );
}

function extractLatestResult(messages: AssistantMessage[]): AssistantResult | null {
  const latest = [...messages].reverse().find((message) => message.role === "assistant" && message.structured);
  return (latest?.structured as AssistantResult | null) || null;
}

function stringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}
