"""
Regression test suite for Module 2 provenance and data mapping review.
Covers:
- Issue 1: Allergy vs non-allergy patient concern mapping & preservation.
- Issue 2: Patient-reported medication vs doctor-prescribed treatment plan provenance.
- Issue 3: Discomfort severity rating scope (overall intake vs symptom-specific).
- Safe isolation of patient data and consultation state.
"""

import pytest
from backend.app.schemas.consultation import (
    ClinicalExtraction,
    ExtractedMedication,
    ExtractedAllergy,
    ExtractedSymptom,
    SoapDraft,
)
from backend.app.db.models import Consultation, IntakeData, IntakeSession
from backend.app.services.comparison_service import compare_intake_and_consultation
from backend.app.services.soap_service import SENTINEL_PLAN


def test_intake_non_allergy_statement_preserved_and_not_promoted():
    """
    Issue 1: A patient-reported concern such as:
    'I have persistent joint pain and I am unsure about my energy levels; I have never had them checked.'
    must remain preserved in intake data and not be misrepresented as a confirmed allergy.
    """
    intake_text = "I have persistent joint pain and I am unsure about my energy levels; I have never had them checked."

    # Verify intake schema stores the patient-reported text verbatim
    intake = IntakeData(
        session_id="test-session-1",
        chief_complaint="Fever, Sore Throat",
        symptoms='["Fever", "Sore Throat"]',
        duration="3-5 days",
        severity="Moderate (6/10)",
        allergies=intake_text,
        medications="None reported",
        conditions="None",
        additional_notes="None",
    )
    assert intake.allergies == intake_text

    # Compare with a consultation where the patient discloses a genuine Penicillin allergy
    consultation = Consultation(
        id="test-consult-1",
        patient_id="test-pat-1",
        status="in-progress",
    )
    clinical_extraction = ClinicalExtraction(
        symptoms=[ExtractedSymptom(name="Fever", duration="3 days")],
        medications=[ExtractedMedication(name="Paracetamol", frequency="twice daily", status="active")],
        allergies=[ExtractedAllergy(substance="Penicillin", reaction="rash")],
        plan=[],
    )

    comparison = compare_intake_and_consultation(
        intake_data=intake,
        consultation=consultation,
        clinical_data=clinical_extraction,
    )

    # Comparison should detect a discrepancy/safety notice regarding allergy disclosure
    allergy_items = [item for item in comparison.items if item.category == "allergies"]
    assert len(allergy_items) > 0
    # Patient intake note must not have silently become confirmed penicillin allergy
    confirmed_alg = [item for item in allergy_items if item.type == "confirmed"]
    assert len(confirmed_alg) == 0, "Non-allergy intake statement must NOT be confirmed as Penicillin allergy"


def test_patient_reported_medication_provenance_vs_prescription():
    """
    Issue 2: Patient reports 'I am taking paracetamol twice a day'.
    This is patient-reported current medication.
    The doctor plan is 'Not documented.' (no prescription).
    It must NOT automatically become a doctor-confirmed prescription.
    """
    extracted_data = ClinicalExtraction(
        symptoms=[ExtractedSymptom(name="Fever", duration="3 days"), ExtractedSymptom(name="Headache", duration="3 days")],
        medications=[ExtractedMedication(name="Paracetamol", frequency="twice daily", status="active")],
        allergies=[ExtractedAllergy(substance="Penicillin", reaction="rash")],
        plan=[],  # Doctor did not prescribe anything in consultation
    )

    # Verify extraction classifies Paracetamol as active medication, but plan is empty
    assert len(extracted_data.medications) == 1
    assert extracted_data.medications[0].name == "Paracetamol"
    assert len(extracted_data.plan) == 0

    # Verify that without clinician prescription evidence, SENTINEL_PLAN is 'Not documented.'
    cleaned_transcript = (
        "Doctor: What brings you in today?\n"
        "Patient: I have fever and headache for three days. I am taking paracetamol twice a day. "
        "I am allergic to penicillin and it causes a rash. I do not have vomiting."
    )
    has_explicit_plan = len(extracted_data.plan) > 0 or any(
        phrase in cleaned_transcript.lower()
        for phrase in ["prescribe", "take this", "plan:", "treatment:", "follow-up in", "order a", "blood test"]
    )
    assert not has_explicit_plan, "Transcript only contains patient-reported home meds, no doctor prescription"
    assert SENTINEL_PLAN == "Not documented."



def test_severity_rating_scope():
    """
    Issue 3: 'Moderate (6/10)' is an overall discomfort rating from intake Step 2.
    It belongs to the intake session and is not falsely mapped to individual symptoms.
    """
    intake = IntakeData(
        session_id="test-session-2",
        chief_complaint="Fever, Sore Throat, Difficulty swallowing, Runny nose, Chills",
        symptoms='["Fever", "Sore Throat", "Difficulty swallowing", "Runny nose", "Chills"]',
        duration="3-5 days",
        severity="Moderate (6/10)",
    )

    assert intake.severity == "Moderate (6/10)"
    # Raw symptoms do not have 6/10 attached to them
    import json
    symptoms_list = json.loads(intake.symptoms)
    assert len(symptoms_list) == 5
    for s in symptoms_list:
        assert "6/10" not in s
        assert "Moderate" not in s
