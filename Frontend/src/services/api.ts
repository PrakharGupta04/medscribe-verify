import type {
  DoctorIntakeSummaryResponse,
  IntakeDraftData,
  IntakeSessionDetailResponse,
  IntakeSubmitRequest,
  IntakeSubmitResponse,
  QueueListResponse,
  SessionCreateResponse,
  ConsultationResponse,
  ConsultationCreateRequest,
  SoapDraftUpdateRequest,
  FinalizeConsultationRequest,
  PipelineRunResponse,
} from '../types/intake';

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

const PIPELINE_TIMEOUT_MS =
  Number(import.meta.env.VITE_PIPELINE_TIMEOUT_MS) || 180000;

async function request<T>(endpoint: string, options?: RequestInit, timeoutMs?: number): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  let response: Response;
  let controller: AbortController | undefined;
  let timeoutId: ReturnType<typeof setTimeout> | undefined;

  if (timeoutMs && timeoutMs > 0) {
    controller = new AbortController();
    timeoutId = setTimeout(() => {
      controller?.abort();
    }, timeoutMs);
  }

  try {
    response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
      signal: controller ? controller.signal : options?.signal,
    });
  } catch (err: unknown) {
    if (err instanceof Error && err.name === 'AbortError') {
      throw new Error(
        `Request timed out after ${Math.round(timeoutMs! / 1000)} seconds. Please try again.`
      );
    }
    const message = err instanceof Error ? err.message : 'Network error';
    throw new Error(`Unable to connect to Medscribe-Verify server (${message}). Ensure the backend is running.`);
  } finally {
    if (timeoutId) {
      clearTimeout(timeoutId);
    }
  }

  if (!response.ok) {
    let errorDetail = `Request failed with status ${response.status}`;
    try {
      const errorJson = await response.json();
      if (errorJson.detail) {
        if (typeof errorJson.detail === 'string') {
          errorDetail = errorJson.detail;
        } else if (Array.isArray(errorJson.detail)) {
          errorDetail = errorJson.detail.map((d: { msg?: string }) => d.msg || '').filter(Boolean).join(', ') || errorDetail;
        }
      }
    } catch {
      // Ignore JSON parse error on non-json error responses
    }
    throw new Error(errorDetail);
  }

  return response.json() as Promise<T>;
}

export const api = {
  /** Create a new temporary patient intake session */
  createSession(): Promise<SessionCreateResponse> {
    return request<SessionCreateResponse>('/intake/sessions', {
      method: 'POST',
    });
  },

  /** Get details and draft data for an intake session */
  getSession(sessionToken: string): Promise<IntakeSessionDetailResponse> {
    return request<IntakeSessionDetailResponse>(`/intake/sessions/${sessionToken}`, {
      method: 'GET',
    });
  },

  /** Save in-progress intake draft answers */
  saveDraft(sessionToken: string, draft: IntakeDraftData): Promise<IntakeSessionDetailResponse> {
    return request<IntakeSessionDetailResponse>(`/intake/sessions/${sessionToken}`, {
      method: 'PUT',
      body: JSON.stringify(draft),
    });
  },

  /** Submit completed patient intake and join the queue */
  submitIntake(sessionToken: string, data: IntakeSubmitRequest): Promise<IntakeSubmitResponse> {
    return request<IntakeSubmitResponse>(`/intake/sessions/${sessionToken}/submit`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  /** Get current queue of waiting and active patients */
  getQueue(): Promise<QueueListResponse> {
    return request<QueueListResponse>('/queue', {
      method: 'GET',
    });
  },

  /** Safely remove/cancel a patient from today's active waiting queue */
  removeFromQueue(queueEntryId: string): Promise<{ message: string; status: string }> {
    return request<{ message: string; status: string }>(`/queue/${queueEntryId}`, {
      method: 'DELETE',
    });
  },

  /** Get doctor pre-consultation intake summary */
  getDoctorIntakeSummary(identifier: string): Promise<DoctorIntakeSummaryResponse> {
    return request<DoctorIntakeSummaryResponse>(`/doctor/intake/${identifier}`, {
      method: 'GET',
    });
  },

  /** Seed demo queue data for isolated testing */
  seedDemoQueue(): Promise<{ message: string; status: string }> {
    return request<{ message: string; status: string }>('/demo/seed', {
      method: 'POST',
    });
  },

  /** Start or retrieve an active consultation for a patient */
  startConsultation(patientId: string, sessionId?: string, forceNew?: boolean): Promise<ConsultationResponse> {
    return request<ConsultationResponse>('/consultations', {
      method: 'POST',
      body: JSON.stringify({
        patient_id: patientId,
        session_id: sessionId || undefined,
        force_new: forceNew || undefined,
      }),
    });
  },

  /** Complete an active consultation visit */
  completeConsultation(consultationId: string): Promise<ConsultationResponse> {
    return request<ConsultationResponse>(`/consultations/${consultationId}/complete`, {
      method: 'POST',
    });
  },

  /** Get a consultation record by ID */
  getConsultation(consultationId: string): Promise<ConsultationResponse> {
    return request<ConsultationResponse>(`/consultations/${consultationId}`, {
      method: 'GET',
    });
  },

  /** Get all consultation visits for a given patient strictly isolated */
  getPatientConsultations(patientId: string): Promise<ConsultationResponse[]> {
    return request<ConsultationResponse[]>(`/consultations/patient/${patientId}`, {
      method: 'GET',
    });
  },

  /** Update and persist the consultation transcript */
  updateConsultationTranscript(
    consultationId: string,
    transcript: string,
    allowClear: boolean = false
  ): Promise<ConsultationResponse> {
    return request<ConsultationResponse>(`/consultations/${consultationId}/transcript`, {
      method: 'PUT',
      body: JSON.stringify({
        transcript,
        allow_clear: allowClear,
      }),
    });
  },

  /** Extract structured clinical facts from the saved consultation transcript */
  extractClinicalInformation(consultationId: string): Promise<ConsultationResponse> {
    return request<ConsultationResponse>(`/consultations/${consultationId}/extract`, {
      method: 'POST',
    });
  },

  /** Generate an AI-assisted SOAP draft note from transcript and clinical extraction */
  generateSoapDraft(consultationId: string): Promise<ConsultationResponse> {
    return request<ConsultationResponse>(`/consultations/${consultationId}/soap-draft`, {
      method: 'POST',
    });
  },

  /** Update and save edited SOAP draft sections */
  updateSoapDraft(
    consultationId: string,
    data: SoapDraftUpdateRequest
  ): Promise<ConsultationResponse> {
    return request<ConsultationResponse>(`/consultations/${consultationId}/soap-draft`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  },

  /** Run the Verification Agent (Agent 3) to verify claims against evidence */
  verifyConsultation(consultationId: string): Promise<ConsultationResponse> {
    return request<ConsultationResponse>(`/consultations/${consultationId}/verify`, {
      method: 'POST',
    });
  },

  /** Run the Comparison / Conflict Intelligence Agent (Agent 4) */
  compareIntakeConsultation(consultationId: string): Promise<ConsultationResponse> {
    return request<ConsultationResponse>(`/consultations/${consultationId}/compare`, {
      method: 'POST',
    });
  },

  /** Run complete consultation intelligence pipeline in one call (Agents 1-4) */
  runPipeline(
    consultationId: string,
    preserveDoctorEdits: boolean = true
  ): Promise<PipelineRunResponse> {
    return request<PipelineRunResponse>(
      `/consultations/${consultationId}/run-pipeline`,
      {
        method: 'POST',
        body: JSON.stringify({
          preserve_doctor_edits: preserveDoctorEdits,
        }),
      },
      PIPELINE_TIMEOUT_MS
    );
  },

  /** Record doctor resolution for a specific Module 1 vs Module 2 discrepancy */
  resolveDiscrepancy(
    consultationId: string,
    itemId: string,
    resolution: string
  ): Promise<ConsultationResponse> {
    return request<ConsultationResponse>(
      `/consultations/${consultationId}/discrepancies/${itemId}/resolve`,
      {
        method: 'PUT',
        body: JSON.stringify({ resolution }),
      }
    );
  },

  /** Finalize consultation record with doctor approval and store final medical record */
  finalizeConsultation(
    consultationId: string,
    data: FinalizeConsultationRequest
  ): Promise<ConsultationResponse> {
    return request<ConsultationResponse>(`/consultations/${consultationId}/finalize`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  /**
   * Download the longitudinal patient record as a PDF blob.
   * Uses a raw fetch (not the JSON request helper) because the response is binary.
   */
  async downloadPatientRecordPdf(patientId: string): Promise<Blob> {
    const url = `${API_BASE_URL}/patients/${patientId}/record/pdf`;
    let response: Response;
    try {
      response = await fetch(url, {
        method: 'GET',
        headers: { Accept: 'application/pdf' },
      });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Network error';
      throw new Error(
        `Unable to connect to Medscribe server (${message}). Ensure the backend is running.`
      );
    }
    if (!response.ok) {
      let errorDetail = `PDF request failed with status ${response.status}`;
      try {
        const errorJson = await response.json();
        if (errorJson.detail && typeof errorJson.detail === 'string') {
          errorDetail = errorJson.detail;
        }
      } catch {
        // Ignore JSON parse error on non-json error responses
      }
      throw new Error(errorDetail);
    }
    return response.blob();
  },

  /** Transcribe audio recording into text for free-text review/editing */
  async transcribeAudio(
    blob: Blob,
    language?: string,
    filename: string = 'recording.webm'
  ): Promise<{ text: string }> {
    const base64 = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => resolve(reader.result as string);
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });

    return request<{ text: string }>('/intake/transcribe', {
      method: 'POST',
      body: JSON.stringify({
        audio_base64: base64,
        filename,
        language: language || undefined,
      }),
    });
  },
};
