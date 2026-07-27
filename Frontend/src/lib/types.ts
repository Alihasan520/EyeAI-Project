export type Language = "en" | "ar";
export type ThemeMode = "light" | "dark" | "system";
export type BackendState = "online" | "warming" | "offline" | "unknown";
export type UserRole = "admin" | "clinician" | string;
export type EyeSide = "left" | "right";

export interface User {
  id: string;
  display_id: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in_seconds: number;
}

export interface BootstrapStatusResponse {
  available: boolean;
  bootstrap_enabled: boolean;
}

export interface HealthResponse {
  status: string;
  model_loaded: boolean;
  model_version: string;
  device: string;
}

export interface AssistantStatusResponse {
  enabled: boolean;
  provider: string;
  model_name: string;
  model_loaded: boolean;
  rag_enabled: boolean;
  rag_loaded: boolean;
  gpu_memory?: {
    allocated_gib?: number;
    reserved_gib?: number;
    peak_allocated_gib?: number;
    peak_reserved_gib?: number;
  };
}

export interface Patient {
  id: string;
  display_id: string;
  medical_record_number: string;
  first_name: string;
  last_name: string;
  date_of_birth: string | null;
  sex: string | null;
  phone: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface PatientInput {
  medical_record_number: string;
  first_name: string;
  last_name: string;
  date_of_birth?: string | null;
  sex?: string | null;
  phone?: string | null;
  notes?: string | null;
}

export interface PatientUpdateInput {
  first_name?: string;
  last_name?: string;
  date_of_birth?: string | null;
  sex?: string | null;
  phone?: string | null;
  notes?: string | null;
}

export interface Visit {
  id: string;
  display_id: string;
  patient_id: string;
  clinician_id: string | null;
  eye: EyeSide;
  visit_date: string;
  notes: string | null;
  created_at: string;
}

export interface VisitListItem {
  visit: Visit;
  patient_display_id: string;
  patient_name: string;
}

export interface DoctorNote {
  id: string;
  display_id: string;
  visit_id: string;
  author_id: string;
  text: string;
  created_at: string;
}


export interface ExplanationArtifact {
  url: string;
  relative_path: string;
  sha256?: string;
  size_bytes?: number;
}

export interface HeatmapPoint {
  pixel?: { x?: number; y?: number };
  normalized?: { x?: number; y?: number };
  region?: string;
  region_ar?: string;
}

export interface ExplanationPayload {
  method?: string;
  target_class_index?: number;
  target_label?: string;
  latency_ms?: number;
  warnings?: string[];
  disclaimer?: string;
  metrics?: Record<string, unknown> & {
    peak?: HeatmapPoint;
    centroid?: HeatmapPoint;
    dominant_region?: Record<string, unknown>;
    tta_map_similarity?: number;
    fundus_focus_fraction?: number;
    border_focus_fraction?: number;
  };
  artifacts?: Record<string, ExplanationArtifact>;
}

export interface StoredPrediction {
  id: string;
  display_id: string;
  visit_id: string;
  request_id: string;
  label: string;
  probability: number;
  threshold: number;
  decision: boolean;
  model_version: string;
  quality_status: string;
  quality: Record<string, unknown>;
  tta: Record<string, unknown>;
  explanation: ExplanationPayload | null;
  created_at: string;
}

export interface TimelineEntry {
  visit: Visit;
  prediction: StoredPrediction | null;
  score_delta: number | null;
  trend: "first_measurement" | "stable" | "increasing" | "decreasing";
  doctor_notes: DoctorNote[];
}

export interface AlertItem {
  id: string;
  display_id: string;
  patient_id: string;
  visit_id: string;
  prediction_id: string;
  alert_type: string;
  severity: string;
  message: string;
  acknowledged: boolean;
  created_at: string;
}

export interface DashboardResponse {
  patients: number;
  visits: number;
  predictions: number;
  unacknowledged_alerts: number;
  recent_alerts: AlertItem[];
}

export interface ApiErrorPayload {
  detail?: string;
  message?: string;
}

export interface AssistantReference {
  citation_number?: number;
  source_id?: string;
  title?: string;
  organization?: string;
  section?: string;
  page?: number | string;
  chunk_id?: string;
  score?: number;
  [key: string]: unknown;
}

export interface AssistantConversation {
  id: string;
  display_id: string;
  patient_id: string;
  visit_id: string | null;
  created_by: string;
  eye: EyeSide;
  title: string | null;
  provider: string;
  model_name: string;
  rag_enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface AssistantMessage {
  id: string;
  display_id: string;
  conversation_id: string;
  role: "user" | "assistant";
  content: string;
  structured: Record<string, unknown> | null;
  references: AssistantReference[];
  created_at: string;
}

export interface AssistantResult {
  answer?: string;
  clinical_interpretation?: string[];
  patient_evidence?: string[];
  references?: AssistantReference[];
  limitations?: string[];
  suggested_review?: string;
  grounding?: Record<string, unknown>;
  heatmap_spatial?: Record<string, unknown>;
  technical_review_profile?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface AssistantTurnResponse {
  user_message: AssistantMessage;
  assistant_message: AssistantMessage;
  result: AssistantResult;
}

export interface AssistantGeneratedDocumentResponse {
  conversation: AssistantConversation;
  result: AssistantResult;
}

export interface ReportRecord {
  id: string;
  display_id: string;
  patient_id: string;
  visit_id: string;
  prediction_id: string;
  download_url: string;
  created_at: string;
}

export interface ReportListItem {
  report: ReportRecord;
  patient_display_id: string;
  patient_name: string;
  visit_display_id: string;
  eye: EyeSide;
  visit_date: string;
}
