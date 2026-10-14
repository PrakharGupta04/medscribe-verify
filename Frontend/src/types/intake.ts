export interface SessionCreateResponse {
  session_token: string;
  status: string;
  expires_at: string;
  created_at: string;
}

export interface IntakeDraftData {
  patient_id?: string;
  mrn?: string;
  name?: string;
  dob?: string;
  phone?: string;
  selected_complaints: string[];
  duration?: string;
  severity?: number;
  additional_symptoms: string[];
  adaptive_answers: Record<string, string>;
  conditions: string[];
  condition_details?: Record<string, Record<string, string>>;
  medications?: string;
  allergies?: string;
  additional_notes?: string;
}

export interface IntakeSessionDetailResponse {
  session_token: string;
  status: 'draft' | 'submitted' | 'expired';
  expires_at: string;
  created_at: string;
  submitted_at?: string | null;
  draft_data?: IntakeDraftData | null;
}

export interface IntakeSubmitRequest {
  patient_id?: string;
  mrn?: string;
  name: string;
  dob?: string;
  phone?: string;
  selected_complaints: string[];
  duration: string;
  severity: number;
  additional_symptoms: string[];
  adaptive_answers: Record<string, string>;
  conditions: string[];
  condition_details?: Record<string, Record<string, string>>;
  medications?: string;
  allergies?: string;
  additional_notes?: string;
}

export interface IntakeSubmitSummary {
  chief_complaint: string;
  symptoms: string[];
  duration: string;
  severity: number;
  conditions: string[];
  condition_details?: Record<string, Record<string, string>>;
  medications: string;
  allergies: string;
  additional_notes: string;
  provenance: string;
}

export interface IntakeSubmitResponse {
  session_token: string;
  patient_id: string;
  mrn: string;
  patient_name: string;
  queue_entry_id: string;
  queue_position: number;
  wait_time_minutes: number;
  submitted_at: string;
  summary: IntakeSubmitSummary;
}

export interface QueueItem {
  id: string;
  position: number | null;
  patient_id: string;
  patient_name: string;
  mrn: string;
  wait_time: string;
  complaint: string;
  intake_status: 'complete' | 'pending';
  status: 'waiting' | 'in-consultation' | 'completed';
  session_id: string;
  submitted_at?: string | null;
}

export interface QueueListResponse {
  items: QueueItem[];
  total_waiting: number;
  total_in_consultation: number;
  total_completed: number;
}

export interface PatientDemographics {
  id: string;
  mrn: string;
  name: string;
  first_name: string;
  age?: string;
  dob?: string;
  phone?: string;
  gender?: string;
}

export interface PreConsultationSummary {
  chief_complaint: string;
  symptoms: string[];
  duration: string;
  severity: number;
  severity_label: string;
  adaptive_responses: Record<string, string>;
  conditions: string[];
  condition_details?: Record<string, Record<string, string>>;
  medications: string;
  allergies: string;
  allergy_flags: string[];
  additional_notes: string;
  submitted_at: string;
  provenance: string;
  clinical_notice: string;
}

export interface DoctorIntakeSummaryResponse {
  patient: PatientDemographics;
  summary: PreConsultationSummary;
  session_id: string;
  queue_id?: string | null;
  queue_status?: string | null;
}

export interface ExtractedSymptom {
  name: string;
  duration?: string | null;
  severity?: string | null;
  onset?: string | null;
  details?: string | null;
}

export interface ExtractedMedication {
  name: string;
  dose?: string | null;
  frequency?: string | null;
  status?: string | null;
}

export interface ExtractedAllergy {
  substance: string;
  reaction?: string | null;
  severity?: string | null;
}

export interface ClinicalExtraction {
  symptoms: ExtractedSymptom[];
  medical_history: string[];
  medications: ExtractedMedication[];
  allergies: ExtractedAllergy[];
  observations: string[];
  diagnoses: string[];
  plan: string[];
  negative_findings: string[];
  provenance: string;
  extracted_at?: string | null;
}

export interface SoapDraft {
  subjective: string;
  objective: string;
  assessment: string;
  plan: string;
  provenance?: string;
  generated_at?: string | null;
  updated_at?: string | null;
}

export interface SoapDraftUpdateRequest {
  subjective: string;
  objective: string;
  assessment: string;
  plan: string;
}

export interface VerificationClaim {
  id: string;
  section: 'subjective' | 'objective' | 'assessment' | 'plan';
  claim: string;
  status: 'supported' | 'unsupported' | 'ambiguous' | 'conflicting';
  source: string;
  evidence: string;
  explanation?: string | null;
}

export interface VerificationResults {
  claims: VerificationClaim[];
  total_claims: number;
  supported_count: number;
  unsupported_count: number;
  ambiguous_count: number;
  conflicting_count: number;
  provenance: string;
  verified_at?: string | null;
}

export interface ComparisonItem {
  id: string;
  category: 'symptoms' | 'medications' | 'allergies' | 'duration' | 'history' | 'general';
  type: 'confirmed' | 'new_in_consultation' | 'not_mentioned_in_consultation' | 'discrepancy';
  label: string;
  intake_value: string;
  consultation_value: string;
  severity: 'info' | 'warning' | 'neutral';
  description: string;
  resolution?: string | null;
  status: 'unresolved' | 'resolved';
}

export interface ComparisonResults {
  items: ComparisonItem[];
  total_items: number;
  confirmed_count: number;
  new_count: number;
  not_mentioned_count: number;
  discrepancy_count: number;
  compared_at?: string | null;
}

export interface FinalMedicalRecord {
  patient_id: string;
  patient_name: string;
  mrn: string;
  consultation_id: string;
  session_id?: string | null;
  visit_date?: string | null;
  soap: SoapDraft;
  doctor_notes?: string | null;
  doctor_name: string;
  status: string;
  approved_at: string;
  provenance: string;
}

export interface FinalizeConsultationRequest {
  subjective?: string;
  objective?: string;
  assessment?: string;
  plan?: string;
  doctor_notes?: string;
  doctor_name?: string;
}

export interface ResolveDiscrepancyRequest {
  resolution: string;
}

export interface ConsultationResponse {
  id: string;
  patient_id: string;
  session_id?: string | null;
  status: string;
  transcript?: string;
  extracted_clinical_data?: ClinicalExtraction | null;
  soap_draft?: SoapDraft | null;
  verification_results?: VerificationResults | null;
  comparison_results?: ComparisonResults | null;
  final_record?: FinalMedicalRecord | null;
  finalized_at?: string | null;
  chief_complaint?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ConsultationCreateRequest {
  patient_id: string;
  session_id?: string;
  force_new?: boolean;
}

