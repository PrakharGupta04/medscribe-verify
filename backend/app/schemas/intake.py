import re
from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class SessionCreateResponse(BaseModel):
    session_token: str
    status: str
    expires_at: datetime
    created_at: datetime


class IntakeDraftData(BaseModel):
    patient_id: Optional[str] = None
    mrn: Optional[str] = None
    name: Optional[str] = ""
    dob: Optional[str] = ""
    phone: Optional[str] = ""
    selected_complaints: List[str] = Field(default_factory=list)
    duration: Optional[str] = "3–5 days"
    severity: Optional[int] = 6
    additional_symptoms: List[str] = Field(default_factory=list)
    adaptive_answers: Dict[str, str] = Field(default_factory=dict)
    conditions: List[str] = Field(default_factory=lambda: ["None of the above"])
    condition_details: Optional[Dict[str, Dict[str, str]]] = Field(default_factory=dict)
    medications: Optional[str] = ""
    allergies: Optional[str] = ""
    additional_notes: Optional[str] = ""


class IntakeSessionDetailResponse(BaseModel):
    session_token: str
    status: str
    expires_at: datetime
    created_at: datetime
    submitted_at: Optional[datetime] = None
    draft_data: Optional[IntakeDraftData] = None


class IntakeSubmitRequest(BaseModel):
    patient_id: Optional[str] = Field(None, description="Existing patient ID for returning patient")
    mrn: Optional[str] = Field(None, description="Existing MRN for returning patient")
    name: str = Field(..., min_length=1, description="Patient full name is required")
    dob: Optional[str] = ""
    phone: Optional[str] = ""
    selected_complaints: List[str] = Field(..., min_length=1, description="At least one chief complaint must be selected")
    duration: str = Field(..., min_length=1, description="Symptom duration is required")
    severity: int = Field(..., ge=1, le=10, description="Severity must be between 1 and 10")
    additional_symptoms: List[str] = Field(default_factory=list)
    adaptive_answers: Dict[str, str] = Field(default_factory=dict)
    conditions: List[str] = Field(default_factory=lambda: ["None of the above"])
    condition_details: Optional[Dict[str, Dict[str, str]]] = Field(default_factory=dict)
    medications: Optional[str] = ""
    allergies: Optional[str] = ""
    additional_notes: Optional[str] = ""

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Patient name cannot be blank")
        return trimmed

    @field_validator("dob")
    @classmethod
    def validate_dob(cls, v: Optional[str]) -> Optional[str]:
        if not v or not v.strip():
            return ""
        trimmed = v.strip()
        # Validate against future date
        today = datetime.now().date()
        parsed_date = None
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
            try:
                parsed_date = datetime.strptime(trimmed, fmt).date()
                break
            except ValueError:
                pass
        if parsed_date is not None:
            if parsed_date > today:
                raise ValueError("Date of birth cannot be in the future.")
        return trimmed

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if not v or not v.strip():
            return ""
        trimmed = v.strip()
        # Clean standard formatting characters
        cleaned = re.sub(r"[\s\-\(\)]", "", trimmed)
        if cleaned.startswith("+91"):
            cleaned = cleaned[3:]
        elif cleaned.startswith("91") and len(cleaned) == 12:
            cleaned = cleaned[2:]
        if not re.match(r"^[6-9]\d{9}$", cleaned):
            raise ValueError("Phone number must be a valid 10-digit mobile number.")
        return cleaned


class IntakeSubmitSummary(BaseModel):
    chief_complaint: str
    symptoms: List[str]
    duration: str
    severity: int
    conditions: List[str]
    condition_details: Dict[str, Dict[str, str]] = Field(default_factory=dict)
    medications: str
    allergies: str
    additional_notes: str
    provenance: str = "patient-reported"


class IntakeSubmitResponse(BaseModel):
    session_token: str
    patient_id: str
    mrn: str
    patient_name: str
    queue_entry_id: str
    queue_position: int
    wait_time_minutes: int
    submitted_at: datetime
    summary: IntakeSubmitSummary


class TranscribeAudioRequest(BaseModel):
    audio_base64: str = Field(..., description="Base64-encoded audio recording")
    filename: Optional[str] = Field(default="audio.webm", description="Original filename with extension")
    language: Optional[str] = Field(default=None, description="Optional language code (en, hi)")


class TranscribeAudioResponse(BaseModel):
    text: str
