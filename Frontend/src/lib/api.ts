import { useAuthStore } from "../features/auth/auth-store";
import { useSettingsStore } from "../features/settings/settings-store";
import { normalizeUrl } from "./format";
import type {
  ApiErrorPayload,
  AssistantStatusResponse,
  BootstrapStatusResponse,
  DashboardResponse,
  EyeSide,
  HealthResponse,
  Patient,
  PatientInput,
  PatientUpdateInput,
  TimelineEntry,
  TokenResponse,
  User,
  StoredPrediction,
  Visit,
  VisitListItem,
  AssistantConversation,
  AssistantMessage,
  AssistantTurnResponse,
  AssistantGeneratedDocumentResponse,
  AssistantResult,
  ReportRecord,
  ReportListItem,
  AlertItem,
} from "./types";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function apiUrl(path: string): string {
  const baseUrl = normalizeUrl(useSettingsStore.getState().apiBaseUrl);
  return `${baseUrl}${path.startsWith("/") ? path : `/${path}`}`;
}

async function parseError(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as ApiErrorPayload;
    return payload.detail || payload.message || response.statusText;
  } catch {
    return response.statusText || "Request failed";
  }
}

export async function apiFetch<T>(
  path: string,
  init: RequestInit = {},
  authenticated = true,
): Promise<T> {
  const token = useAuthStore.getState().accessToken;
  const headers = new Headers(init.headers);

  if (!headers.has("Content-Type") && init.body && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  if (authenticated && token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(apiUrl(path), {
    ...init,
    headers,
  });

  if (!response.ok) {
    const message = await parseError(response);
    if (response.status === 401 && authenticated) {
      useAuthStore.getState().clearSession();
    }
    throw new ApiError(message, response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export function getHealth(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>("/health", {}, false);
}

export function getBootstrapStatus(): Promise<BootstrapStatusResponse> {
  return apiFetch<BootstrapStatusResponse>("/api/v1/auth/bootstrap-status", {}, false);
}

export function bootstrapWorkspace(payload: {
  email: string;
  full_name: string;
  password: string;
}): Promise<User> {
  return apiFetch<User>(
    "/api/v1/auth/bootstrap",
    { method: "POST", body: JSON.stringify(payload) },
    false,
  );
}

export function getAssistantStatus(): Promise<AssistantStatusResponse> {
  return apiFetch<AssistantStatusResponse>("/api/v1/assistant/status");
}

export function getDashboard(): Promise<DashboardResponse> {
  return apiFetch<DashboardResponse>("/api/v1/dashboard");
}

export async function login(email: string, password: string): Promise<User> {
  const token = await apiFetch<TokenResponse>(
    "/api/v1/auth/login",
    {
      method: "POST",
      body: JSON.stringify({ email, password }),
    },
    false,
  );

  useAuthStore.setState({ accessToken: token.access_token });

  try {
    const user = await apiFetch<User>("/api/v1/auth/me");
    useAuthStore.getState().setSession(token.access_token, user);
    return user;
  } catch (error) {
    useAuthStore.getState().clearSession();
    throw error;
  }
}

export function updateMyProfile(payload: { email?: string; full_name?: string }): Promise<User> {
  return apiFetch<User>("/api/v1/auth/me", {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function changeMyPassword(payload: {
  current_password: string;
  new_password: string;
}): Promise<void> {
  return apiFetch<void>("/api/v1/auth/change-password", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listUsers(): Promise<User[]> {
  return apiFetch<User[]>("/api/v1/users");
}

export function createUser(payload: {
  email: string;
  full_name: string;
  password: string;
  role: "admin" | "clinician";
}): Promise<User> {
  return apiFetch<User>("/api/v1/users", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateUserAccount(
  userRef: string,
  payload: { email?: string; full_name?: string; role?: "admin" | "clinician"; is_active?: boolean },
): Promise<User> {
  return apiFetch<User>(`/api/v1/users/${encodeURIComponent(userRef)}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function resetUserPassword(userRef: string, newPassword: string): Promise<User> {
  return apiFetch<User>(`/api/v1/users/${encodeURIComponent(userRef)}/reset-password`, {
    method: "POST",
    body: JSON.stringify({ new_password: newPassword }),
  });
}

export function listPatients(search = ""): Promise<Patient[]> {
  const query = search.trim() ? `?search=${encodeURIComponent(search.trim())}` : "";
  return apiFetch<Patient[]>(`/api/v1/patients${query}`);
}

export function getPatient(patientRef: string): Promise<Patient> {
  return apiFetch<Patient>(`/api/v1/patients/${encodeURIComponent(patientRef)}`);
}

export function createPatient(payload: PatientInput): Promise<Patient> {
  return apiFetch<Patient>("/api/v1/patients", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updatePatient(patientRef: string, payload: PatientUpdateInput): Promise<Patient> {
  return apiFetch<Patient>(`/api/v1/patients/${encodeURIComponent(patientRef)}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function createVisit(
  patientRef: string,
  payload: { eye: EyeSide; visit_date?: string | null; notes?: string | null },
): Promise<Visit> {
  return apiFetch<Visit>(`/api/v1/patients/${encodeURIComponent(patientRef)}/visits`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listVisits(filters: { patientId?: string; eye?: EyeSide } = {}): Promise<VisitListItem[]> {
  const params = new URLSearchParams();
  if (filters.patientId) params.set("patient_id", filters.patientId);
  if (filters.eye) params.set("eye", filters.eye);
  const suffix = params.size ? `?${params.toString()}` : "";
  return apiFetch<VisitListItem[]>(`/api/v1/visits${suffix}`);
}

export function getVisit(visitRef: string): Promise<Visit> {
  return apiFetch<Visit>(`/api/v1/visits/${encodeURIComponent(visitRef)}`);
}

export function analyzeVisit(
  visitRef: string,
  file: File,
  explanation = true,
): Promise<StoredPrediction> {
  const formData = new FormData();
  formData.append("file", file);
  return apiFetch<StoredPrediction>(
    `/api/v1/visits/${encodeURIComponent(visitRef)}/analyze?explanation=${explanation ? "true" : "false"}`,
    { method: "POST", body: formData },
  );
}

export function buildArtifactUrl(relativeOrAbsoluteUrl: string): string {
  if (/^https?:\/\//i.test(relativeOrAbsoluteUrl)) return relativeOrAbsoluteUrl;
  return `${normalizeUrl(useSettingsStore.getState().apiBaseUrl)}${
    relativeOrAbsoluteUrl.startsWith("/") ? relativeOrAbsoluteUrl : `/${relativeOrAbsoluteUrl}`
  }`;
}

export function getTimeline(patientRef: string, eye?: EyeSide): Promise<TimelineEntry[]> {
  const suffix = eye ? `?eye=${eye}` : "";
  return apiFetch<TimelineEntry[]>(
    `/api/v1/patients/${encodeURIComponent(patientRef)}/timeline${suffix}`,
  );
}

export async function testBackendConnection(baseUrl: string): Promise<HealthResponse> {
  const response = await fetch(`${normalizeUrl(baseUrl)}/health`, {
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new ApiError(await parseError(response), response.status);
  }

  return (await response.json()) as HealthResponse;
}


export function createAssistantConversation(
  patientRef: string,
  payload: { eye: EyeSide; visit_id?: string | null; title?: string | null },
): Promise<AssistantConversation> {
  return apiFetch<AssistantConversation>(
    `/api/v1/patients/${encodeURIComponent(patientRef)}/assistant/conversations`,
    { method: "POST", body: JSON.stringify(payload) },
  );
}

export function listAssistantConversations(patientRef: string): Promise<AssistantConversation[]> {
  return apiFetch<AssistantConversation[]>(
    `/api/v1/patients/${encodeURIComponent(patientRef)}/assistant/conversations`,
  );
}

export function listAssistantMessages(conversationRef: string): Promise<AssistantMessage[]> {
  return apiFetch<AssistantMessage[]>(
    `/api/v1/assistant/conversations/${encodeURIComponent(conversationRef)}/messages`,
  );
}

export function sendAssistantMessage(
  conversationRef: string,
  content: string,
): Promise<AssistantTurnResponse> {
  return apiFetch<AssistantTurnResponse>(
    `/api/v1/assistant/conversations/${encodeURIComponent(conversationRef)}/messages`,
    { method: "POST", body: JSON.stringify({ content }) },
  );
}

export function generateVisitAssistantSummary(
  visitRef: string,
): Promise<AssistantGeneratedDocumentResponse> {
  return apiFetch<AssistantGeneratedDocumentResponse>(
    `/api/v1/visits/${encodeURIComponent(visitRef)}/assistant-summary`,
    { method: "POST" },
  );
}

export function generateReportDraft(
  visitRef: string,
): Promise<AssistantGeneratedDocumentResponse> {
  return apiFetch<AssistantGeneratedDocumentResponse>(
    `/api/v1/visits/${encodeURIComponent(visitRef)}/report-draft`,
    { method: "POST" },
  );
}

export function createReport(
  visitRef: string,
  payload: {
    clinical_summary?: string | null;
    references?: Record<string, unknown>[];
  } = {},
): Promise<ReportRecord> {
  return apiFetch<ReportRecord>(
    `/api/v1/visits/${encodeURIComponent(visitRef)}/reports`,
    { method: "POST", body: JSON.stringify(payload) },
  );
}

export function listReports(patientId?: string): Promise<ReportListItem[]> {
  const suffix = patientId ? `?patient_id=${encodeURIComponent(patientId)}` : "";
  return apiFetch<ReportListItem[]>(`/api/v1/reports${suffix}`);
}


export function listAlerts(patientId?: string): Promise<AlertItem[]> {
  const suffix = patientId ? `?patient_id=${encodeURIComponent(patientId)}` : "";
  return apiFetch<AlertItem[]>(`/api/v1/alerts${suffix}`);
}

export function acknowledgeAlert(alertRef: string): Promise<AlertItem> {
  return apiFetch<AlertItem>(
    `/api/v1/alerts/${encodeURIComponent(alertRef)}/acknowledge`,
    { method: "POST" },
  );
}

export function reportDownloadUrl(report: ReportRecord): string {
  return buildArtifactUrl(report.download_url);
}

export async function fetchAuthenticatedFile(path: string): Promise<Blob> {
  const token = useAuthStore.getState().accessToken;
  const targetUrl = /^https?:\/\//i.test(path) ? path : apiUrl(path);
  const response = await fetch(targetUrl, {
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });
  if (!response.ok) throw new ApiError(await parseError(response), response.status);
  return response.blob();
}

export async function downloadAuthenticatedFile(path: string, filename: string): Promise<void> {
  const blob = await fetchAuthenticatedFile(path);
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(objectUrl);
}

export function resultAnswer(result: AssistantResult | null | undefined): string {
  if (!result) return "";
  return typeof result.answer === "string" ? result.answer : "";
}
