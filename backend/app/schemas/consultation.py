import json
from datetime import datetime
from typing import List, Optional, Union
from pydantic import BaseModel, ConfigDict, Field, field_validator


class ExtractedSymptom(BaseModel):
    name: str = Field(..., description="Name of the symptom")
    duration: Optional[str] = Field(None, description="Duration explicitly mentioned, or null")
    severity: Optional[str] = Field(None, description="Severity explicitly mentioned (e.g. 6/10, severe, mild), or null")
    onset: Optional[str] = Field(None, description="Onset timing if explicitly mentioned, or null")
    details: Optional[str] = Field(None, description="Additional context explicitly mentioned, or null")


class ExtractedMedication(BaseModel):
    name: str = Field(..., description="Medication name")
    dose: Optional[str] = Field(None, description="Dose if explicitly mentioned, or null")
    frequency: Optional[str] = Field(None, description="Frequency if explicitly mentioned (e.g. twice daily), or null")
    status: Optional[str] = Field(None, description="Status if explicitly mentioned (e.g. active, stopped yesterday, PRN), or null")


class ExtractedAllergy(BaseModel):
    substance: str = Field(..., description="Allergen substance (e.g. penicillin)")
    reaction: Optional[str] = Field(None, description="Reaction explicitly mentioned (e.g. rash), or null")
    severity: Optional[str] = Field(None, description="Severity if explicitly mentioned, or null")


class ClinicalExtraction(BaseModel):
    symptoms: List[ExtractedSymptom] = Field(default_factory=list, description="Explicit symptoms")
    medical_history: List[str] = Field(default_factory=list, description="Past medical history explicitly mentioned")
    medications: List[ExtractedMedication] = Field(default_factory=list, description="Explicit medications")
    allergies: List[ExtractedAllergy] = Field(default_factory=list, description="Explicit allergies and reactions")
    observations: List[str] = Field(default_factory=list, description="Explicit clinical observations, vitals, or physical exam findings")
    diagnoses: List[str] = Field(default_factory=list, description="Explicit clinical diagnoses or suspected conditions stated by doctor")
    plan: List[str] = Field(default_factory=list, description="Explicit plan or next steps stated")
    negative_findings: List[str] = Field(default_factory=list, description="Explicitly denied symptoms or negative findings (e.g. denies vomiting)")
    provenance: str = Field("ai-extracted", description="Provenance marker: ai-extracted, unverified")
    extracted_at: Optional[datetime] = None


class SoapDraft(BaseModel):
    subjective: str = Field(..., description="Subjective summary of patient-reported symptoms, history, meds, allergies, and negative findings")
    objective: str = Field(..., description="Objective findings or 'Not documented.'")
    assessment: str = Field(..., description="Clinician-authored or explicitly documented clinician assessment, or 'Not explicitly documented.'")
    plan: str = Field(..., description="Clinician-authored or explicitly documented treatment plan, tests, instructions or 'Not documented.'")
    provenance: str = Field("ai-generated-draft-unverified", description="Provenance marker: AI-Generated · Draft · Unverified")
    generated_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SoapDraftUpdateRequest(BaseModel):
    subjective: str = Field(..., description="Subjective notes")
    objective: str = Field(..., description="Objective findings")
    assessment: str = Field(..., description="Clinical assessment / diagnosis")
    plan: str = Field(..., description="Clinical plan and next steps")


class VerificationClaim(BaseModel):
    id: str = Field(..., description="Unique claim identifier, e.g. claim-1")
    section: str = Field(..., description="SOAP section: subjective, objective, assessment, plan")
    claim: str = Field(..., description="Specific factual claim asserted in the SOAP note")
    status: str = Field(..., description="supported, unsupported, ambiguous, conflicting")
    source: str = Field("consultation-transcript", description="consultation-transcript, clinical-extraction, not-documented, or none")
    evidence: str = Field(..., description="Exact or grounded evidence snippet from transcript/facts, or notice of absence")
    explanation: Optional[str] = Field(None, description="Clinical or verification reasoning")


class VerificationResults(BaseModel):
    claims: List[VerificationClaim] = Field(default_factory=list)
    total_claims: int = 0
    supported_count: int = 0
    unsupported_count: int = 0
    ambiguous_count: int = 0
    conflicting_count: int = 0
    provenance: str = Field("ai-verified", description="Provenance marker: ai-verified")
    verified_at: Optional[datetime] = None


class ComparisonItem(BaseModel):
    id: str = Field(..., description="Unique item identifier, e.g. comp-1")
    category: str = Field(..., description="symptoms, medications, allergies, duration, history, general")
    type: str = Field(..., description="confirmed, new_in_consultation, not_mentioned_in_consultation, discrepancy")
    label: str = Field(..., description="Clinical subject, e.g. 'Medication', 'Penicillin Allergy', 'Duration'")
    intake_value: str = Field(..., description="Value reported by patient in Module 1 intake")
    consultation_value: str = Field(..., description="Value discussed/observed in Module 2 consultation")
    severity: str = Field("info", description="info, warning, neutral")
    description: str = Field(..., description="Neutral comparison description")
    resolution: Optional[str] = Field(None, description="Doctor resolution or confirmation note")
    status: str = Field("unresolved", description="unresolved, resolved")


class ComparisonResults(BaseModel):
    items: List[ComparisonItem] = Field(default_factory=list)
    total_items: int = 0
    confirmed_count: int = 0
    new_count: int = 0
    not_mentioned_count: int = 0
    discrepancy_count: int = 0
    compared_at: Optional[datetime] = None


class FinalMedicalRecord(BaseModel):
    patient_id: str
    patient_name: str
    mrn: str
    consultation_id: str
    session_id: Optional[str] = None
    visit_date: Optional[str] = None
    soap: SoapDraft
    doctor_notes: Optional[str] = None
    doctor_name: str = "Dr. J. Patel"
    status: str = "doctor-approved"
    approved_at: datetime
    provenance: str = "doctor-approved-final-record"


class FinalizeConsultationRequest(BaseModel):
    subjective: Optional[str] = None
    objective: Optional[str] = None
    assessment: Optional[str] = None
    plan: Optional[str] = None
    doctor_notes: Optional[str] = None
    doctor_name: Optional[str] = "Dr. J. Patel"


class ResolveDiscrepancyRequest(BaseModel):
    resolution: str = Field(..., description="Doctor's clinical resolution for the discrepancy")


class ConsultationCreateRequest(BaseModel):
    patient_id: str = Field(..., description="ID of the patient from Module 1")
    session_id: Optional[str] = Field(None, description="Optional associated intake session ID")
    force_new: Optional[bool] = Field(False, description="If True, completes active visit and starts a new visit for this patient")


class ConsultationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    patient_id: str
    session_id: Optional[str] = None
    status: str = "in-progress"
    transcript: Optional[str] = ""
    extracted_clinical_data: Optional[ClinicalExtraction] = None
    soap_draft: Optional[SoapDraft] = None
    verification_results: Optional[VerificationResults] = None
    comparison_results: Optional[ComparisonResults] = None
    final_record: Optional[FinalMedicalRecord] = None
    finalized_at: Optional[datetime] = None
    chief_complaint: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    @field_validator("extracted_clinical_data", mode="before")
    @classmethod
    def parse_extracted_clinical_data(cls, v: Union[str, dict, None, ClinicalExtraction]):
        if isinstance(v, str) and v.strip():
            try:
                parsed = json.loads(v)
                return parsed
            except Exception:
                return None
        return v

    @field_validator("soap_draft", mode="before")
    @classmethod
    def parse_soap_draft(cls, v: Union[str, dict, None, SoapDraft]):
        if isinstance(v, str) and v.strip():
            try:
                parsed = json.loads(v)
                return parsed
            except Exception:
                return None
        return v

    @field_validator("verification_results", mode="before")
    @classmethod
    def parse_verification_results(cls, v: Union[str, dict, None, VerificationResults]):
        if isinstance(v, str) and v.strip():
            try:
                parsed = json.loads(v)
                return parsed
            except Exception:
                return None
        return v

    @field_validator("comparison_results", mode="before")
    @classmethod
    def parse_comparison_results(cls, v: Union[str, dict, None, ComparisonResults]):
        if isinstance(v, str) and v.strip():
            try:
                parsed = json.loads(v)
                return parsed
            except Exception:
                return None
        return v

    @field_validator("final_record", mode="before")
    @classmethod
    def parse_final_record(cls, v: Union[str, dict, None, FinalMedicalRecord]):
        if isinstance(v, str) and v.strip():
            try:
                parsed = json.loads(v)
                return parsed
            except Exception:
                return None
        return v


class ConsultationTranscriptUpdateRequest(BaseModel):
    transcript: str = Field(..., description="Consultation transcript text (raw or edited)")
    allow_clear: Optional[bool] = Field(False, description="Explicit flag allowing clearing of an existing transcript")

