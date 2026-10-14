from typing import Dict, List, Optional
from pydantic import BaseModel


class PatientDemographics(BaseModel):
    id: str
    mrn: str
    name: str
    first_name: str
    age: Optional[str] = "—"
    dob: Optional[str] = "—"
    phone: Optional[str] = "—"
    gender: str = "Not specified"


class PreConsultationSummary(BaseModel):
    chief_complaint: str
    symptoms: List[str]
    duration: str
    severity: int
    severity_label: str
    adaptive_responses: Dict[str, str]
    conditions: List[str]
    condition_details: Dict[str, Dict[str, str]] = {}
    medications: str
    allergies: str
    allergy_flags: List[str]
    additional_notes: str
    submitted_at: str
    provenance: str = "patient-reported"
    clinical_notice: str


class DoctorIntakeSummaryResponse(BaseModel):
    patient: PatientDemographics
    summary: PreConsultationSummary
    session_id: str
    queue_id: Optional[str] = None
    queue_status: Optional[str] = None
