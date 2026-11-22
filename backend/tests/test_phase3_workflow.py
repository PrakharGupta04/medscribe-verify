from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.db.models import Consultation, IntakeData, Patient
from backend.app.services.comparison_service import (
    compare_intake_and_consultation,
    is_negative_allergy_statement,
)
from backend.app.schemas.consultation import (
    ClinicalExtraction,
    ExtractedSymptom,
    ExtractedAllergy,
)


def test_is_negative_allergy_statement():
    """Verify that clinical allergy denials and negative statements are recognized,
    while actual allergies, empty values, None, whitespace, and 'not documented' return False.
    """
    # Explicit negative statements (no allergies) -> True
    assert is_negative_allergy_statement("No known drug allergies (NKDA).") is True
    assert is_negative_allergy_statement("No known drug allergies (NKDA)") is True
    assert is_negative_allergy_statement("NKDA") is True
    assert is_negative_allergy_statement("nkda") is True
    assert is_negative_allergy_statement("None") is True
    assert is_negative_allergy_statement("None reported") is True
    assert is_negative_allergy_statement("No known allergies") is True
    assert is_negative_allergy_statement("No allergies") is True
    assert is_negative_allergy_statement("Denies allergies") is True

    # Real clinical allergies (must NOT be treated as negative) -> False
    assert is_negative_allergy_statement("Penicillin") is False
    assert is_negative_allergy_statement("Amoxicillin - rash") is False
    assert is_negative_allergy_statement("Sulfa drugs") is False
    assert is_negative_allergy_statement("Latex allergy") is False
    assert is_negative_allergy_statement("Peanuts") is False

    # None, empty strings, whitespace, and "not documented" represent unknown/undocumented status -> False
    assert is_negative_allergy_statement(None) is False
    assert is_negative_allergy_statement("") is False
    assert is_negative_allergy_statement("   ") is False
    assert is_negative_allergy_statement("\t\n") is False
    assert is_negative_allergy_statement("not documented") is False
    assert is_negative_allergy_statement("Not documented") is False
    assert is_negative_allergy_statement("Not documented.") is False


def test_comparison_nkda_intake_does_not_create_false_allergy_alert(db_session: Session):
    """Verify that intake reporting NKDA and consultation with no allergies does not create a false alert."""
    patient = Patient(name="NKDA Patient", mrn="MRN-TEST-NKDA")
    db_session.add(patient)
    db_session.commit()

    intake = IntakeData(
        patient_id=patient.id,
        session_id=str(patient.id),
        allergies="No known drug allergies (NKDA).",
        chief_complaint="Fever",
        duration="1 day",
        severity=3,
        symptoms="[]",
        conditions="[]",
        medications="None",
    )
    db_session.add(intake)

    consultation = Consultation(
        patient_id=patient.id,
        transcript="Doctor: Any fever? Patient: Yes, since yesterday.",
        extracted_clinical_data=ClinicalExtraction(
            symptoms=[ExtractedSymptom(name="Fever", duration="1 day")],
            allergies=[],
        ).model_dump_json(),
    )
    db_session.add(consultation)
    db_session.commit()

    results = compare_intake_and_consultation(intake, consultation)
    allergy_items = [i for i in results.items if i.category == "allergies"]
    # No false allergy alert should be generated when patient reported NKDA
    assert len(allergy_items) == 0


def test_comparison_missing_allergy_info_does_not_create_false_allergy_alert(db_session: Session):
    """Verify that missing allergy information (None, empty string, whitespace, 'Not documented')
    does not become a confirmed allergy, an NKDA statement, or a false discrepancy/alert.
    """
    patient = Patient(name="Missing Allergy Patient", mrn="MRN-TEST-MISSING-ALG")
    db_session.add(patient)
    db_session.commit()

    for missing_val in [None, "", "   ", "Not documented", "Not documented."]:
        intake = IntakeData(
            patient_id=patient.id,
            session_id=str(patient.id),
            allergies=missing_val,
            chief_complaint="Headache",
            duration="1 day",
            severity=2,
            symptoms="[]",
            conditions="[]",
            medications="None",
        )
        consultation = Consultation(
            patient_id=patient.id,
            transcript="Doctor: How is the headache? Patient: Mild.",
            extracted_clinical_data=ClinicalExtraction(
                symptoms=[ExtractedSymptom(name="Headache", duration="1 day")],
                allergies=[],
            ).model_dump_json(),
        )
        results = compare_intake_and_consultation(intake, consultation)
        allergy_items = [i for i in results.items if i.category == "allergies"]
        assert len(allergy_items) == 0, f"Expected 0 allergy items for allergies={missing_val!r}, got {allergy_items}"


def test_comparison_ai_extracted_negative_statement_not_treated_as_allergy(db_session: Session):
    """Verify that explicit negative statements or 'Not documented' extracted by the AI are not treated as actual allergies."""
    patient = Patient(name="Neg AI Patient", mrn="MRN-TEST-NEG-AI")
    db_session.add(patient)
    db_session.commit()

    intake = IntakeData(
        patient_id=patient.id,
        session_id=str(patient.id),
        allergies="No known drug allergies (NKDA).",
        chief_complaint="Cough",
        duration="3 days",
        severity=2,
        symptoms="[]",
        conditions="[]",
        medications="None",
    )
    db_session.add(intake)

    consultation = Consultation(
        patient_id=patient.id,
        transcript="Doctor: Any allergies? Patient: No known drug allergies.",
        extracted_clinical_data=ClinicalExtraction(
            symptoms=[ExtractedSymptom(name="Cough", duration="3 days")],
            allergies=[
                ExtractedAllergy(substance="No known drug allergies"),
                ExtractedAllergy(substance="Not documented"),
            ],
        ).model_dump_json(),
    )
    db_session.add(consultation)
    db_session.commit()

    results = compare_intake_and_consultation(intake, consultation)
    allergy_items = [i for i in results.items if i.category == "allergies"]
    assert len(allergy_items) == 0


def test_comparison_missing_intake_allergy_with_disclosed_consultation_allergy(db_session: Session):
    """Verify that when intake has missing allergy info and consultation discloses an allergy,
    it becomes a newly disclosed allergy (info), not a discrepancy or confirmed allergy.
    """
    patient = Patient(name="Disclosed Alg Patient", mrn="MRN-TEST-DISC-ALG")
    db_session.add(patient)
    db_session.commit()

    intake = IntakeData(
        patient_id=patient.id,
        session_id=str(patient.id),
        allergies=None,
        chief_complaint="Fever",
        duration="1 day",
        severity=3,
        symptoms="[]",
        conditions="[]",
        medications="None",
    )
    db_session.add(intake)

    consultation = Consultation(
        patient_id=patient.id,
        transcript="Doctor: Do you have any allergies? Patient: Yes, Penicillin gives me hives.",
        extracted_clinical_data=ClinicalExtraction(
            symptoms=[ExtractedSymptom(name="Fever", duration="1 day")],
            allergies=[ExtractedAllergy(substance="Penicillin", reaction="hives")],
        ).model_dump_json(),
    )
    db_session.add(consultation)
    db_session.commit()

    results = compare_intake_and_consultation(intake, consultation)
    allergy_items = [i for i in results.items if i.category == "allergies"]
    assert len(allergy_items) == 1
    assert allergy_items[0].type == "new_in_consultation"
    assert allergy_items[0].severity == "info"
    assert "Penicillin" in allergy_items[0].consultation_value


def test_comparison_real_allergy_not_discussed_creates_legitimate_safety_alert(db_session: Session):
    """Verify that intake reporting a genuine allergy (Penicillin) not discussed creates a legitimate alert."""
    patient = Patient(name="Allergy Patient", mrn="MRN-TEST-ALG")
    db_session.add(patient)
    db_session.commit()

    intake = IntakeData(
        patient_id=patient.id,
        session_id=str(patient.id),
        allergies="Penicillin - severe anaphylaxis",
        chief_complaint="Cough",
        duration="2 days",
        severity=4,
        symptoms="[]",
        conditions="[]",
        medications="None",
    )
    db_session.add(intake)

    consultation = Consultation(
        patient_id=patient.id,
        transcript="Doctor: How long have you had the cough? Patient: 2 days.",
        extracted_clinical_data=ClinicalExtraction(
            symptoms=[ExtractedSymptom(name="Cough", duration="2 days")],
            allergies=[],
        ).model_dump_json(),
    )
    db_session.add(consultation)
    db_session.commit()

    results = compare_intake_and_consultation(intake, consultation)
    allergy_items = [i for i in results.items if i.category == "allergies"]
    assert len(allergy_items) == 1
    item = allergy_items[0]
    assert item.type == "not_mentioned_in_consultation"
    assert item.severity == "warning"
    assert "Penicillin" in item.description


def test_resolve_discrepancy_empty_note_rejected(client: TestClient, db_session: Session):
    """Verify that attempting to resolve a discrepancy with an empty or whitespace note returns HTTP 400."""
    patient = Patient(name="Discrepancy Patient", mrn="MRN-TEST-DISC")
    db_session.add(patient)
    db_session.commit()

    consultation = Consultation(
        patient_id=patient.id,
        transcript="Doctor: Hello.",
        comparison_results='{"items": [{"id": "comp-sym-1", "category": "symptoms", "type": "discrepancy", "label": "Duration", "intake_value": "3 days", "consultation_value": "1 week", "severity": "warning", "description": "Diff", "resolution": null, "status": "unresolved"}], "total_items": 1, "confirmed_count": 0, "new_count": 0, "not_mentioned_count": 0, "discrepancy_count": 1}',
    )
    db_session.add(consultation)
    db_session.commit()

    # Empty note
    res_empty = client.put(
        f"/api/consultations/{consultation.id}/discrepancies/comp-sym-1/resolve",
        json={"resolution": ""},
    )
    assert res_empty.status_code == 400
    assert "cannot be empty" in res_empty.json()["detail"].lower()

    # Whitespace note
    res_ws = client.put(
        f"/api/consultations/{consultation.id}/discrepancies/comp-sym-1/resolve",
        json={"resolution": "    \t  "},
    )
    assert res_ws.status_code == 400
    assert "cannot be empty" in res_ws.json()["detail"].lower()


def test_resolve_discrepancy_on_finalized_consultation_rejected(client: TestClient, db_session: Session):
    """Verify that resolving discrepancies on a finalized consultation is rejected with HTTP 400."""
    patient = Patient(name="Finalized Patient", mrn="MRN-TEST-FIN")
    db_session.add(patient)
    db_session.commit()

    consultation = Consultation(
        patient_id=patient.id,
        transcript="Doctor: Hello.",
        status="completed",
        finalized_at=datetime.now(timezone.utc),
        final_record='{"doctor_name": "Dr. Test"}',
        comparison_results='{"items": [{"id": "comp-sym-1", "category": "symptoms", "type": "discrepancy", "label": "Duration", "intake_value": "3 days", "consultation_value": "1 week", "severity": "warning", "description": "Diff", "resolution": null, "status": "unresolved"}], "total_items": 1, "confirmed_count": 0, "new_count": 0, "not_mentioned_count": 0, "discrepancy_count": 1}',
    )
    db_session.add(consultation)
    db_session.commit()

    res = client.put(
        f"/api/consultations/{consultation.id}/discrepancies/comp-sym-1/resolve",
        json={"resolution": "Patient clarified it was 1 week."},
    )
    assert res.status_code == 400
    assert "finalized" in res.json()["detail"].lower()


def test_finalize_consultation_success_and_doctor_provenance(client: TestClient, db_session: Session):
    """Verify that finalizing creates a doctor-approved final record with correct provenance."""
    patient = Patient(name="Approval Patient", mrn="MRN-TEST-APPR")
    db_session.add(patient)
    db_session.commit()

    consultation = Consultation(
        patient_id=patient.id,
        transcript="Doctor: Hello.",
        soap_draft='{"subjective": "Sub", "objective": "Obj", "assessment": "Ass", "plan": "Plan"}',
    )
    db_session.add(consultation)
    db_session.commit()

    res_fin = client.post(
        f"/api/consultations/{consultation.id}/finalize",
        json={"doctor_name": "Dr. Jane Smith"},
    )
    assert res_fin.status_code == 200
    data = res_fin.json()
    assert data["status"] == "completed"
    assert data["final_record"]["doctor_name"] == "Dr. Jane Smith"
    assert data["final_record"]["provenance"] == "doctor-approved-final-record"


def test_cannot_finalize_already_finalized_consultation(client: TestClient, db_session: Session):
    """Verify that calling finalize on an already finalized record returns HTTP 400."""
    patient = Patient(name="Already Finalized", mrn="MRN-TEST-ALREADY")
    db_session.add(patient)
    db_session.commit()

    consultation = Consultation(
        patient_id=patient.id,
        transcript="Doctor: Hello.",
        soap_draft='{"subjective": "Sub", "objective": "Obj", "assessment": "Ass", "plan": "Plan"}',
        status="completed",
        finalized_at=datetime.now(timezone.utc),
        final_record='{"doctor_name": "Dr. First Attending"}',
    )
    db_session.add(consultation)
    db_session.commit()

    res = client.post(
        f"/api/consultations/{consultation.id}/finalize",
        json={"doctor_name": "Dr. Second Attending"},
    )
    assert res.status_code == 400
    assert "already been finalized" in res.json()["detail"].lower()
