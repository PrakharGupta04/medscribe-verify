import json
from datetime import datetime
from typing import Dict, List, Tuple
from backend.app.db.models import IntakeData, Patient
from backend.app.schemas.doctor import (
    DoctorIntakeSummaryResponse,
    PatientDemographics,
    PreConsultationSummary,
)

CLINICAL_DISCLAIMER = (
    "This summary was generated deterministically from the patient's self-reported intake form. "
    "It has not been clinically verified and does not make diagnostic or therapeutic decisions. "
    "All information must be reviewed and confirmed by a doctor during consultation."
)

ADAPTIVE_QUESTION_LABELS = {
    "Fever-0": "Fever Onset",
    "Fever-1": "Temperature Measured",
    "Sore Throat-0": "Swallowing Discomfort",
    "Sore Throat-1": "Throat White Patches",
    "Cough-0": "Cough Type",
    "Cough-1": "Cough Duration",
    "Stomach Pain-0": "Pain Location",
    "Stomach Pain-1": "Pain Pattern",
    "Headache-0": "Headache Location",
    "Headache-1": "Associated Symptoms",
}

SYMPTOM_LABELS = {
    "diff_swallow": "Difficulty swallowing",
    "ear_pain": "Ear pain",
    "runny_nose": "Runny nose",
    "chills": "Chills",
    "rash": "Rash",
    "nausea": "Nausea",
    "fatigue": "Fatigue",
    "loss_appetite": "Loss of appetite",
}


def get_severity_label(severity: int) -> str:
    if severity <= 3:
        return f"Mild ({severity}/10)"
    elif severity <= 6:
        return f"Moderate ({severity}/10)"
    else:
        return f"Severe ({severity}/10)"


def screen_allergy_flags(allergies_text: str) -> List[str]:
    flags = []
    if not allergies_text:
        return flags
    lower = allergies_text.lower()
    if "penicillin" in lower or "amoxicillin" in lower:
        flags.append("Penicillin / Beta-lactam allergy noted (patient-reported)")
    if "sulfa" in lower or "sulfonamide" in lower:
        flags.append("Sulfa drug allergy noted (patient-reported)")
    if "latex" in lower:
        flags.append("Latex allergy noted (patient-reported)")
    if "anaphylaxis" in lower or "severe" in lower:
        flags.append("Patient noted severe/anaphylactic reaction risk")
    return flags


CONDITION_QUESTION_MAPPINGS = {
    "Diabetes-0": ("Diabetes", "type"),
    "Diabetes-1": ("Diabetes", "treatment"),
    "High blood pressure-0": ("High blood pressure", "medication"),
    "High blood pressure-1": ("High blood pressure", "last_reading"),
    "Asthma-0": ("Asthma", "inhaler_frequency"),
    "Asthma-1": ("Asthma", "recent_flare_up"),
    "Heart disease-0": ("Heart disease", "condition_type"),
    "Heart disease-1": ("Heart disease", "medication"),
    "Thyroid condition-0": ("Thyroid condition", "condition_type"),
    "Thyroid condition-1": ("Thyroid condition", "medication"),
    "Kidney disease-0": ("Kidney disease", "dialysis"),
    "Kidney disease-1": ("Kidney disease", "restrictions"),
}


def build_pre_consult_summary(
    patient: Patient,
    intake: IntakeData,
    session_id: str,
    queue_id: str = None,
    queue_status: str = None,
) -> DoctorIntakeSummaryResponse:
    try:
        symptoms_list = json.loads(intake.symptoms) if intake.symptoms else []
    except Exception:
        symptoms_list = [intake.symptoms] if intake.symptoms else []

    try:
        raw_adaptive = json.loads(intake.adaptive_responses) if intake.adaptive_responses else {}
    except Exception:
        raw_adaptive = {}

    condition_details: Dict[str, Dict[str, str]] = {}

    # 1. Check if structured condition_details was explicitly embedded in raw_adaptive
    if "__condition_details__" in raw_adaptive and isinstance(raw_adaptive["__condition_details__"], dict):
        condition_details = dict(raw_adaptive["__condition_details__"])

    # 2. Extract from raw_adaptive condition keys if not already present
    for k, v in raw_adaptive.items():
        if k in CONDITION_QUESTION_MAPPINGS:
            cond, field = CONDITION_QUESTION_MAPPINGS[k]
            if cond not in condition_details:
                condition_details[cond] = {"provenance": "patient-reported"}
            condition_details[cond][field] = v

    # 3. Backward compatibility: Parse legacy condition details string from additional_notes if needed
    cleaned_notes = intake.additional_notes or ""
    if "Condition details:" in cleaned_notes:
        import re
        match = re.search(r"Condition details:\s*(.*?)(?:\n|$)", cleaned_notes)
        if match:
            legacy_str = match.group(1).strip()
            if not condition_details:
                items = legacy_str.split("; ")
                for item in items:
                    sub_match = re.match(r"^([^()]+)\s*\(([^()]+)\):\s*(.+)$", item.strip())
                    if sub_match:
                        cond = sub_match.group(1).strip()
                        q_text = sub_match.group(2).strip()
                        ans = sub_match.group(3).strip()
                        if cond not in condition_details:
                            condition_details[cond] = {"provenance": "patient-reported"}
                        field_key = q_text
                        q_lower = q_text.lower()
                        if "type" in q_lower:
                            field_key = "type"
                        elif "medication" in q_lower or "insulin" in q_lower:
                            field_key = "treatment" if cond == "Diabetes" else "medication"
                        elif "reading" in q_lower:
                            field_key = "last_reading"
                        elif "inhaler" in q_lower:
                            field_key = "inhaler_frequency"
                        elif "flare" in q_lower:
                            field_key = "recent_flare_up"
                        elif "dialysis" in q_lower:
                            field_key = "dialysis"
                        condition_details[cond][field_key] = ans
            cleaned_notes = cleaned_notes.replace(match.group(0), "").strip()

    # Map symptom follow-up questionnaire responses only (exclude condition answers & internal keys)
    adaptive_mapped = {}
    for k, v in raw_adaptive.items():
        if k == "__condition_details__" or k in CONDITION_QUESTION_MAPPINGS:
            continue
        label = ADAPTIVE_QUESTION_LABELS.get(k, k)
        adaptive_mapped[label] = v

    try:
        conditions_list = json.loads(intake.conditions) if intake.conditions else []
    except Exception:
        conditions_list = [intake.conditions] if intake.conditions else []

    # Map symptoms codes to readable names if needed
    formatted_symptoms = []
    for s in symptoms_list:
        formatted_symptoms.append(SYMPTOM_LABELS.get(s, s))

    submitted_str = intake.submitted_at.strftime("%H:%M, %d %b %Y") if intake.submitted_at else "Just now"

    first_name = patient.name.split()[0] if patient.name else "Patient"

    demographics = PatientDemographics(
        id=patient.id,
        mrn=patient.mrn,
        name=patient.name,
        first_name=first_name,
        age="28" if "1998" in (patient.dob or "") else ("—" if not patient.dob else patient.dob),
        dob=patient.dob or "—",
        phone=patient.phone or "—",
        gender=patient.gender or "Not specified",
    )

    summary = PreConsultationSummary(
        chief_complaint=intake.chief_complaint,
        symptoms=formatted_symptoms,
        duration=intake.duration,
        severity=intake.severity,
        severity_label=get_severity_label(intake.severity),
        adaptive_responses=adaptive_mapped,
        conditions=conditions_list,
        condition_details=condition_details,
        medications=intake.medications or "None reported",
        allergies=intake.allergies or "None reported",
        allergy_flags=screen_allergy_flags(intake.allergies or ""),
        additional_notes=cleaned_notes if cleaned_notes else "None provided",
        submitted_at=submitted_str,
        provenance="patient-reported",
        clinical_notice=CLINICAL_DISCLAIMER,
    )

    return DoctorIntakeSummaryResponse(
        patient=demographics,
        summary=summary,
        session_id=session_id,
        queue_id=queue_id,
        queue_status=queue_status,
    )
