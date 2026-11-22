from datetime import datetime, timezone, timedelta
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.db.models import Consultation, IntakeData, Patient
from backend.app.schemas.consultation import (
    ClinicalExtraction,
    ExtractedSymptom,
    ExtractedMedication,
    ExtractedAllergy,
    SoapDraft,
)


def _setup_patient_and_consultation(
    client: TestClient,
    db_session: Session,
    transcript: str = "Doctor: Hello, what symptoms do you have?\nPatient: I have a cough and mild fever.",
) -> tuple[str, str]:
    """Helper to seed intake and consultation with realistic test data."""
    token = client.post("/api/intake/sessions").json()["session_token"]
    sub_res = client.post(
        f"/api/intake/sessions/{token}/submit",
        json={
            "name": "Pipeline Test Patient",
            "dob": "1992-03-15",
            "phone": "9876540202",
            "selected_complaints": ["Cough"],
            "duration": "3 days",
            "severity": 4,
            "additional_symptoms": [],
            "conditions": [],
            "medications": "None",
            "allergies": "None",
        },
    )
    assert sub_res.status_code == 200
    patient_id = sub_res.json()["patient_id"]

    cons_res = client.post(
        "/api/consultations",
        json={"patient_id": patient_id, "session_id": token},
    )
    assert cons_res.status_code == 201
    consultation_id = cons_res.json()["id"]

    if transcript:
        client.put(
            f"/api/consultations/{consultation_id}/transcript",
            json={"transcript": transcript},
        )

    return patient_id, consultation_id


def _mock_clinical_extraction():
    return ClinicalExtraction(
        symptoms=[ExtractedSymptom(name="Cough", duration="3 days")],
        medications=[ExtractedMedication(name="Paracetamol", dose="500mg")],
        allergies=[ExtractedAllergy(substance="None", reaction="")],
        negative_findings=["No chest pain"],
        diagnoses=["Upper respiratory tract infection"],
        plan=["Hydration and rest"],
    )


def _mock_soap_draft(now=None):
    if now is None:
        now = datetime.now(timezone.utc)
    return SoapDraft(
        subjective="Patient reports cough for 3 days. Denies chest pain.",
        objective="Not documented.",
        assessment="Upper respiratory tract infection.",
        plan="Hydration and rest.",
        provenance="ai-generated-draft-unverified",
        generated_at=now,
        updated_at=now,
    )


# 1. Successful execution of all stages
def test_run_pipeline_successful_execution_all_stages(client: TestClient, db_session: Session):
    _, cons_id = _setup_patient_and_consultation(client, db_session)

    mock_ext = _mock_clinical_extraction()
    mock_soap = _mock_soap_draft()

    with patch("backend.app.services.extraction_service.extract_clinical_facts_groq", return_value=mock_ext), \
         patch("backend.app.services.soap_service.generate_soap_draft_groq", return_value=mock_soap):
        res = client.post(f"/api/consultations/{cons_id}/run-pipeline")

    assert res.status_code == 200
    data = res.json()
    assert data["completed"] is True
    assert len(data["stages"]) == 4

    stage_names = [s["name"] for s in data["stages"]]
    assert stage_names == ["extraction", "soap_generation", "verification", "comparison"]
    for s in data["stages"]:
        assert s["status"] == "completed"
        assert s["duration_ms"] >= 0.0

    consultation = data["consultation"]
    assert consultation["extracted_clinical_data"] is not None
    assert consultation["soap_draft"] is not None
    assert consultation["verification_results"] is not None
    assert consultation["comparison_results"] is not None


# 2. Finalized consultation rejected before stage execution
def test_run_pipeline_finalized_rejected_before_stages(client: TestClient, db_session: Session):
    _, cons_id = _setup_patient_and_consultation(client, db_session)

    # Mark consultation as finalized
    cons = db_session.query(Consultation).filter(Consultation.id == cons_id).first()
    cons.finalized_at = datetime.now(timezone.utc)
    cons.final_record = '{"patient_id": "test", "doctor_name": "Dr. Test"}'
    cons.status = "finalized"
    db_session.commit()

    with patch("backend.app.services.consultation_service.extract_and_save_clinical_data") as mock_extract:
        res = client.post(f"/api/consultations/{cons_id}/run-pipeline")
        mock_extract.assert_not_called()

    assert res.status_code == 400
    assert "finalized" in res.json()["detail"].lower()


# 3. Empty transcript rejected before stage execution
def test_run_pipeline_empty_transcript_rejected_before_stages(client: TestClient, db_session: Session):
    _, cons_id = _setup_patient_and_consultation(client, db_session, transcript="")

    with patch("backend.app.services.consultation_service.extract_and_save_clinical_data") as mock_extract:
        res = client.post(f"/api/consultations/{cons_id}/run-pipeline")
        mock_extract.assert_not_called()

    assert res.status_code == 400
    assert "transcript is empty" in res.json()["detail"].lower()

    # Also test whitespace-only transcript
    client.put(
        f"/api/consultations/{cons_id}/transcript",
        json={"transcript": "   \n\t  ", "allow_clear": True},
    )
    res_ws = client.post(f"/api/consultations/{cons_id}/run-pipeline")
    assert res_ws.status_code == 400
    assert "transcript is empty" in res_ws.json()["detail"].lower()


# 4. Stage failure is recorded correctly and skips dependent stages
def test_run_pipeline_stage_failure_recorded_and_skips_dependents(client: TestClient, db_session: Session):
    _, cons_id = _setup_patient_and_consultation(client, db_session)

    with patch(
        "backend.app.services.extraction_service.extract_clinical_facts_groq",
        side_effect=RuntimeError("Groq extraction API timeout"),
    ):
        res = client.post(f"/api/consultations/{cons_id}/run-pipeline")

    assert res.status_code == 200
    data = res.json()
    assert data["completed"] is False

    stages = {s["name"]: s for s in data["stages"]}
    assert stages["extraction"]["status"] == "failed"
    assert "Extraction failed" in stages["extraction"]["detail"]
    assert stages["soap_generation"]["status"] == "skipped"
    assert stages["verification"]["status"] == "skipped"
    assert stages["comparison"]["status"] == "skipped"


# 5. Doctor-edited SOAP is preserved
def test_run_pipeline_preserves_doctor_edited_soap(client: TestClient, db_session: Session):
    _, cons_id = _setup_patient_and_consultation(client, db_session)

    # Doctor previously edited this SOAP draft: updated_at > generated_at
    base_time = datetime.now(timezone.utc) - timedelta(hours=1)
    edit_time = datetime.now(timezone.utc)
    edited_soap = SoapDraft(
        subjective="CLINICIAN OVERRIDE: Patient has chronic refractory migraine for 5 years.",
        objective="Blood pressure 130/85.",
        assessment="Chronic migraine without aura.",
        plan="Topiramate 25mg daily.",
        provenance="doctor-reviewed",
        generated_at=base_time,
        updated_at=edit_time,
    )
    cons = db_session.query(Consultation).filter(Consultation.id == cons_id).first()
    cons.soap_draft = edited_soap.model_dump_json()
    db_session.commit()

    mock_ext = _mock_clinical_extraction()

    with patch("backend.app.services.extraction_service.extract_clinical_facts_groq", return_value=mock_ext), \
         patch("backend.app.services.soap_service.generate_soap_draft_groq") as mock_generate_soap:
        res = client.post(
            f"/api/consultations/{cons_id}/run-pipeline",
            json={"preserve_doctor_edits": True},
        )
        mock_generate_soap.assert_not_called()

    assert res.status_code == 200
    data = res.json()
    assert data["completed"] is True
    stages = {s["name"]: s for s in data["stages"]}
    assert stages["soap_generation"]["status"] == "skipped"
    assert "Doctor-edited SOAP draft preserved" in stages["soap_generation"]["detail"]

    # Verify subjective was preserved exactly
    soap = data["consultation"]["soap_draft"]
    assert "CLINICIAN OVERRIDE" in soap["subjective"]


# 6. Non-edited SOAP can be regenerated according to the timestamp rule
def test_run_pipeline_regenerates_non_edited_soap(client: TestClient, db_session: Session):
    _, cons_id = _setup_patient_and_consultation(client, db_session)

    # Existing AI draft that was NOT doctor-edited: updated_at == generated_at
    creation_time = datetime.now(timezone.utc) - timedelta(hours=2)
    original_ai_soap = SoapDraft(
        subjective="Old AI subjective text.",
        objective="Not documented.",
        assessment="Not explicitly documented.",
        plan="Not documented.",
        provenance="ai-generated-draft-unverified",
        generated_at=creation_time,
        updated_at=creation_time,
    )
    cons = db_session.query(Consultation).filter(Consultation.id == cons_id).first()
    cons.soap_draft = original_ai_soap.model_dump_json()
    db_session.commit()

    mock_ext = _mock_clinical_extraction()
    fresh_soap = SoapDraft(
        subjective="Fresh AI regenerated subjective text.",
        objective="Not documented.",
        assessment="Viral pharyngitis.",
        plan="Hydration.",
        provenance="ai-generated-draft-unverified",
        generated_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    with patch("backend.app.services.extraction_service.extract_clinical_facts_groq", return_value=mock_ext), \
         patch("backend.app.services.soap_service.generate_soap_draft_groq", return_value=fresh_soap):
        res = client.post(
            f"/api/consultations/{cons_id}/run-pipeline",
            json={"preserve_doctor_edits": True},
        )

    assert res.status_code == 200
    data = res.json()
    stages = {s["name"]: s for s in data["stages"]}
    assert stages["soap_generation"]["status"] == "completed"
    assert data["consultation"]["soap_draft"]["subjective"] == "Fresh AI regenerated subjective text."


# 7. Response contains correct stage results and updated consultation
def test_run_pipeline_response_structure_and_types(client: TestClient, db_session: Session):
    _, cons_id = _setup_patient_and_consultation(client, db_session)

    mock_ext = _mock_clinical_extraction()
    mock_soap = _mock_soap_draft()

    with patch("backend.app.services.extraction_service.extract_clinical_facts_groq", return_value=mock_ext), \
         patch("backend.app.services.soap_service.generate_soap_draft_groq", return_value=mock_soap):
        # Optional request body test: calling without payload
        res = client.post(f"/api/consultations/{cons_id}/run-pipeline")

    assert res.status_code == 200
    data = res.json()
    assert isinstance(data["completed"], bool)
    assert isinstance(data["stages"], list)
    assert len(data["stages"]) == 4

    for stage in data["stages"]:
        assert "name" in stage
        assert "status" in stage
        assert "detail" in stage
        assert "duration_ms" in stage
        assert isinstance(stage["duration_ms"], (int, float))

    consultation = data["consultation"]
    assert consultation["id"] == cons_id
    assert consultation["status"] in ("in-progress", "completed")
    assert isinstance(consultation["created_at"], str)
    assert isinstance(consultation["updated_at"], str)
