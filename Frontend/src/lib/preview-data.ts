import type { Patient, TimelineEntry, User, VisitListItem } from "./types";

const now = new Date();
const isoDaysAgo = (days: number) => new Date(now.getTime() - days * 86_400_000).toISOString();

export const previewPatients: Patient[] = [
  {
    id: "preview-patient-1",
    display_id: "PAT-000014",
    medical_record_number: "MRN-240014",
    first_name: "Sarah",
    last_name: "Ahmed",
    date_of_birth: "1958-03-18",
    sex: "female",
    phone: "+1 555 014 228",
    notes: "Requires image-quality review before final interpretation.",
    created_at: isoDaysAgo(410),
    updated_at: isoDaysAgo(3),
  },
  {
    id: "preview-patient-2",
    display_id: "PAT-000021",
    medical_record_number: "MRN-240021",
    first_name: "Omar",
    last_name: "Hassan",
    date_of_birth: "1964-11-02",
    sex: "male",
    phone: "+1 555 021 907",
    notes: "Longitudinal right-eye review.",
    created_at: isoDaysAgo(300),
    updated_at: isoDaysAgo(12),
  },
  {
    id: "preview-patient-3",
    display_id: "PAT-000028",
    medical_record_number: "MRN-240028",
    first_name: "Maya",
    last_name: "Nasser",
    date_of_birth: "1971-07-25",
    sex: "female",
    phone: null,
    notes: null,
    created_at: isoDaysAgo(140),
    updated_at: isoDaysAgo(26),
  },
];

export const previewTimeline: TimelineEntry[] = [
  {
    visit: {
      id: "preview-visit-1",
      display_id: "VIS-20260118-000001",
      patient_id: previewPatients[0].id,
      clinician_id: "preview-user",
      eye: "right",
      visit_date: isoDaysAgo(190),
      notes: "Baseline right-eye screening.",
      created_at: isoDaysAgo(190),
    },
    prediction: {
      id: "preview-prediction-1",
      display_id: "ANA-20260118-000001",
      visit_id: "preview-visit-1",
      request_id: "preview-request-1",
      label: "Non-AMD",
      probability: 0.28,
      threshold: 0.335,
      decision: false,
      model_version: "retfound-run09-tta-v1",
      quality_status: "acceptable",
      quality: { warnings: [] },
      tta: { absolute_disagreement: 0.025 },
      explanation: null,
      created_at: isoDaysAgo(190),
    },
    score_delta: null,
    trend: "first_measurement",
    doctor_notes: [],
  },
  {
    visit: {
      id: "preview-visit-2",
      display_id: "VIS-20260723-000001",
      patient_id: previewPatients[0].id,
      clinician_id: "preview-user",
      eye: "right",
      visit_date: isoDaysAgo(3),
      notes: "Current screening with possible blur.",
      created_at: isoDaysAgo(3),
    },
    prediction: {
      id: "preview-prediction-2",
      display_id: "ANA-20260723-000001",
      visit_id: "preview-visit-2",
      request_id: "preview-request-2",
      label: "AMD",
      probability: 0.8009,
      threshold: 0.335,
      decision: true,
      model_version: "retfound-run09-tta-v1",
      quality_status: "review_required",
      quality: { warnings: ["possible_blur"] },
      tta: { absolute_disagreement: 0.0637 },
      explanation: null,
      created_at: isoDaysAgo(3),
    },
    score_delta: 0.5209,
    trend: "increasing",
    doctor_notes: [
      {
        id: "preview-note-1",
        display_id: "NOT-000001",
        visit_id: "preview-visit-2",
        author_id: "preview-user",
        text: "Review image quality and correlate with macular findings.",
        created_at: isoDaysAgo(3),
      },
    ],
  },
];

export const previewVisits: VisitListItem[] = [
  ...previewTimeline.map((entry) => ({
    visit: entry.visit,
    patient_display_id: previewPatients[0].display_id,
    patient_name: `${previewPatients[0].first_name} ${previewPatients[0].last_name}`,
  })),
  {
    visit: {
      id: "preview-visit-3",
      display_id: "VIS-20260714-000002",
      patient_id: previewPatients[1].id,
      clinician_id: "preview-user",
      eye: "left",
      visit_date: isoDaysAgo(12),
      notes: "Routine left-eye follow-up.",
      created_at: isoDaysAgo(12),
    },
    patient_display_id: previewPatients[1].display_id,
    patient_name: `${previewPatients[1].first_name} ${previewPatients[1].last_name}`,
  },
];

export const previewUsers: User[] = [
  {
    id: "preview-user",
    display_id: "USR-000001",
    email: "demo@eyeai.local",
    full_name: "Dr. Lina Morgan",
    role: "admin",
    is_active: true,
    created_at: isoDaysAgo(420),
  },
  {
    id: "preview-user-2",
    display_id: "USR-000002",
    email: "clinician@eyeai.local",
    full_name: "Dr. Adam Reed",
    role: "clinician",
    is_active: true,
    created_at: isoDaysAgo(210),
  },
];
