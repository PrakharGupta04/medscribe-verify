"""
Module 3: Longitudinal Patient Records — Automated Tests.

All tests use an isolated in-memory SQLite database; none touch the real
application database or any seeded patient records.

Coverage:
- Chronological consultation ordering
- PDF endpoint: valid patient → 200, application/pdf, valid %PDF header
- PDF endpoint: invalid patient_id → 404
- PDF endpoint: patient with no consultations → 400
- Patient data isolation (patient A's PDF does not contain patient B's MRN)
- Visit history deduplication (2 consultations → 2 items in list)
- PDF handles missing SOAP gracefully (in-progress visit with no SOAP)
- Correct visit_number count for 3 consultations (service layer)
- Medication with missing status → "Not documented" (not "Active")
- AI-extracted allergy not incorrectly labelled as doctor-reviewed
- Finalized visit with no final SOAP → draft labelled AI-generated, not doctor-approved
- Special characters in patient/clinical text do not break PDF generation
- Malformed intake conditions JSON does not crash PDF generation
- Isolated visit-history regression: two consultations on same patient_id are distinct rows
"""
import json
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db.base import Base
from backend.app.db.models import Consultation, IntakeData, IntakeSession, Patient
from backend.app.db.session import get_db
from backend.app.main import app


# ---------------------------------------------------------------------------
# Fixtures — isolated in-memory database, never touches real medscribe.db
# ---------------------------------------------------------------------------

SQLALCHEMY_DATABASE_URL = "sqlite://"  # pure in-memory; discarded after session


@pytest.fixture(scope="module")
def engine():
    _engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=_engine)
    yield _engine
    Base.metadata.drop_all(bind=_engine)


@pytest.fixture(scope="module")
def db_session(engine):
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture(scope="module")
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utc_now():
    return datetime.now(timezone.utc)


def _make_patient(db, name="Test Patient", mrn=None) -> Patient:
    mrn = mrn or f"MRN-TEST-{uuid.uuid4().hex[:8].upper()}"
    p = Patient(
        id=str(uuid.uuid4()),
        mrn=mrn,
        name=name,
        dob="1980-01-01",
        phone="555-0000",
        gender="Not specified",
        created_at=_utc_now(),
        updated_at=_utc_now(),
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _make_session(db, patient_id: str) -> IntakeSession:
    s = IntakeSession(
        id=str(uuid.uuid4()),
        session_token=str(uuid.uuid4()),
        patient_id=patient_id,
        status="submitted",
        expires_at=_utc_now(),
        submitted_at=_utc_now(),
        created_at=_utc_now(),
        updated_at=_utc_now(),
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def _make_intake(
    db,
    session_id: str,
    patient_id: str,
    complaint: str = "Chest pain",
    medications: str = "Lisinopril 10mg",
    allergies: str = "Penicillin",
    conditions: str = None,
) -> IntakeData:
    intake = IntakeData(
        id=str(uuid.uuid4()),
        session_id=session_id,
        patient_id=patient_id,
        chief_complaint=complaint,
        symptoms=json.dumps(["Chest tightness"]),
        duration="2 days",
        severity=6,
        adaptive_responses=json.dumps({}),
        conditions=conditions if conditions is not None else json.dumps(["Hypertension"]),
        medications=medications,
        allergies=allergies,
        provenance="patient-reported",
        created_at=_utc_now(),
        submitted_at=_utc_now(),
    )
    db.add(intake)
    db.commit()
    db.refresh(intake)
    return intake


def _make_consultation(
    db,
    patient_id: str,
    session_id: str,
    status: str = "completed",
    with_soap: bool = True,
    with_final: bool = True,
    with_final_soap: bool = True,
    doctor_name: str = "Dr. Smith",
    extracted_clinical_data: str = None,
) -> Consultation:
    soap = None
    final = None
    if with_soap:
        soap = json.dumps({
            "subjective": "Patient reports chest pain for 2 days.",
            "objective": "BP 130/85, HR 78.",
            "assessment": "Hypertensive urgency.",
            "plan": "Continue Lisinopril. Follow up in 1 week.",
            "provenance": "ai-generated-draft-unverified",
        })
    if with_final:
        final_dict = {
            "patient_id": patient_id,
            "patient_name": "Test Patient",
            "mrn": "MRN-TEST",
            "consultation_id": "cid",
            "doctor_name": doctor_name,
            "status": "completed",
            "approved_at": _utc_now().isoformat(),
            "provenance": "doctor-approved-final-record",
        }
        if with_final_soap:
            final_dict["soap"] = {
                "subjective": "Patient reports chest pain for 2 days.",
                "objective": "BP 130/85.",
                "assessment": "Hypertensive urgency.",
                "plan": "Continue Lisinopril.",
            }
        final = json.dumps(final_dict)

    c = Consultation(
        id=str(uuid.uuid4()),
        patient_id=patient_id,
        session_id=session_id,
        status=status,
        transcript="Doctor: How are you? Patient: I have chest pain.",
        soap_draft=soap,
        final_record=final,
        extracted_clinical_data=extracted_clinical_data,
        finalized_at=_utc_now() if with_final else None,
        created_at=_utc_now(),
        updated_at=_utc_now(),
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


# ---------------------------------------------------------------------------
# Tests: visit ordering
# ---------------------------------------------------------------------------

def test_patient_consultations_chronological_order(client, db_session):
    """GET /consultations/patient/{id} returns visits ordered newest-first."""
    p = _make_patient(db_session, name="Order Patient")
    s1 = _make_session(db_session, p.id)
    s2 = _make_session(db_session, p.id)
    _make_intake(db_session, s1.id, p.id, "Visit 1 complaint")
    _make_intake(db_session, s2.id, p.id, "Visit 2 complaint")
    _make_consultation(db_session, p.id, s1.id)
    _make_consultation(db_session, p.id, s2.id)

    resp = client.get(f"/api/consultations/patient/{p.id}")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 2
    dates = [item["created_at"] for item in items]
    assert dates == sorted(dates, reverse=True), "Expected newest-first ordering"


# ---------------------------------------------------------------------------
# Tests: PDF endpoint
# ---------------------------------------------------------------------------

def test_patient_pdf_endpoint_valid_patient(client, db_session):
    """GET /patients/{id}/record/pdf returns 200, application/pdf, valid %PDF header."""
    p = _make_patient(db_session, name="PDF Patient")
    s = _make_session(db_session, p.id)
    _make_intake(db_session, s.id, p.id, "Headache")
    _make_consultation(db_session, p.id, s.id)

    resp = client.get(f"/api/patients/{p.id}/record/pdf")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    assert resp.headers.get("content-type", "").startswith("application/pdf")
    assert resp.content[:4] == b"%PDF", "Response body is not a valid PDF"


def test_patient_pdf_endpoint_contains_mrn(client, db_session):
    """The PDF contains the patient's MRN string somewhere in the binary content."""
    p = _make_patient(db_session, name="MRN Check Patient", mrn="MRN-TEST-MRNCHECK")
    s = _make_session(db_session, p.id)
    _make_intake(db_session, s.id, p.id, "Knee pain")
    _make_consultation(db_session, p.id, s.id)

    resp = client.get(f"/api/patients/{p.id}/record/pdf")
    assert resp.status_code == 200
    assert b"MRN-TEST-MRNCHECK" in resp.content


def test_patient_pdf_endpoint_invalid_patient_id(client):
    """GET /patients/{invalid_id}/record/pdf returns 404."""
    resp = client.get("/api/patients/non-existent-patient-id/record/pdf")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_patient_pdf_endpoint_no_consultations_returns_400(client, db_session):
    """GET /patients/{id}/record/pdf returns 400 if patient has no consultations."""
    p = _make_patient(db_session, name="Empty Patient")
    # Intentionally no consultations
    resp = client.get(f"/api/patients/{p.id}/record/pdf")
    assert resp.status_code == 400
    assert "no consultation records" in resp.json()["detail"].lower()


def test_patient_pdf_excludes_other_patient_data(client, db_session):
    """Patient A's PDF must not contain Patient B's MRN."""
    pa = _make_patient(db_session, name="Patient Alpha", mrn="MRN-TEST-ALPHA")
    pb = _make_patient(db_session, name="Patient Beta", mrn="MRN-TEST-BETA")

    sa = _make_session(db_session, pa.id)
    sb = _make_session(db_session, pb.id)
    _make_intake(db_session, sa.id, pa.id, "Alpha complaint")
    _make_intake(db_session, sb.id, pb.id, "Beta complaint")
    _make_consultation(db_session, pa.id, sa.id)
    _make_consultation(db_session, pb.id, sb.id)

    resp = client.get(f"/api/patients/{pa.id}/record/pdf")
    assert resp.status_code == 200
    assert b"MRN-TEST-BETA" not in resp.content, "Patient B's MRN leaked into Patient A's PDF"


# ---------------------------------------------------------------------------
# Tests: visit history
# ---------------------------------------------------------------------------

def test_visit_history_no_duplicate_entries(client, db_session):
    """A patient with 2 consultations returns exactly 2 items in the visit list."""
    p = _make_patient(db_session, name="Two Visit Patient")
    s1 = _make_session(db_session, p.id)
    s2 = _make_session(db_session, p.id)
    _make_intake(db_session, s1.id, p.id, "First complaint")
    _make_intake(db_session, s2.id, p.id, "Second complaint")
    _make_consultation(db_session, p.id, s1.id, status="completed")
    _make_consultation(db_session, p.id, s2.id, status="in-progress", with_final=False)

    resp = client.get(f"/api/consultations/patient/{p.id}")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 2, f"Expected 2 visits, got {len(items)}"


def test_pdf_handles_missing_soap_gracefully(client, db_session):
    """Visit with no SOAP draft does not crash PDF generation."""
    p = _make_patient(db_session, name="No SOAP Patient")
    s = _make_session(db_session, p.id)
    _make_intake(db_session, s.id, p.id, "Routine checkup")
    _make_consultation(db_session, p.id, s.id, with_soap=False, with_final=False, status="in-progress")

    resp = client.get(f"/api/patients/{p.id}/record/pdf")
    assert resp.status_code == 200
    assert resp.content[:4] == b"%PDF"


def test_pdf_visit_count_in_response(db_session):
    """record_service returns correct total_visits=3 and chronological visit_number sequence."""
    from backend.app.services.record_service import get_patient_longitudinal_record

    p = _make_patient(db_session, name="Three Visit Patient")
    for i in range(3):
        s = _make_session(db_session, p.id)
        _make_intake(db_session, s.id, p.id, f"Complaint {i + 1}")
        _make_consultation(db_session, p.id, s.id)

    record = get_patient_longitudinal_record(db_session, p.id)
    assert record["total_visits"] == 3
    assert len(record["visits"]) == 3
    visit_numbers = [v["visit_number"] for v in record["visits"]]
    assert visit_numbers == [1, 2, 3]


# ---------------------------------------------------------------------------
# Tests: medication status
# ---------------------------------------------------------------------------

def test_medication_missing_status_is_not_documented(db_session):
    """Medications with no status field must appear as 'Not documented', never 'Active'."""
    from backend.app.services.record_service import get_patient_longitudinal_record

    p = _make_patient(db_session, name="Med Status Patient")
    s = _make_session(db_session, p.id)
    _make_intake(db_session, s.id, p.id, "Hypertension follow-up")

    # Extracted data with one med that has no status
    extracted = json.dumps({
        "symptoms": [],
        "medical_history": [],
        "medications": [
            {"name": "Amlodipine", "dose": "5mg", "frequency": "once daily", "status": None},
            {"name": "Metformin", "dose": "500mg", "frequency": None, "status": ""},
        ],
        "allergies": [],
        "observations": [],
        "diagnoses": [],
        "plan": [],
        "negative_findings": [],
        "provenance": "ai-extracted",
    })
    _make_consultation(
        db_session, p.id, s.id,
        with_soap=False, with_final=False, status="in-progress",
        extracted_clinical_data=extracted,
    )

    record = get_patient_longitudinal_record(db_session, p.id)
    assert record["total_visits"] == 1
    meds = record["visits"][0]["medications"]
    assert len(meds) == 2

    for med in meds:
        assert med["status"] == "Not documented", (
            f"Expected 'Not documented' for medication with no status, got '{med['status']}'"
        )

    # Confirm "Active" is not silently injected
    all_statuses = {m["status"] for m in meds}
    assert "Active" not in all_statuses, "Implicit 'Active' status must not be inferred"


def test_medication_explicit_status_preserved(db_session):
    """Medications with an explicit status retain that value."""
    from backend.app.services.record_service import get_patient_longitudinal_record

    p = _make_patient(db_session, name="Med Explicit Status Patient")
    s = _make_session(db_session, p.id)
    _make_intake(db_session, s.id, p.id, "Diabetes review")

    extracted = json.dumps({
        "symptoms": [],
        "medical_history": [],
        "medications": [
            {"name": "Insulin", "dose": "10 units", "frequency": "nightly", "status": "active"},
            {"name": "Metformin", "dose": "1g", "frequency": "twice daily", "status": "stopped yesterday"},
        ],
        "allergies": [],
        "observations": [],
        "diagnoses": [],
        "plan": [],
        "negative_findings": [],
        "provenance": "ai-extracted",
    })
    _make_consultation(
        db_session, p.id, s.id,
        with_soap=False, with_final=False, status="in-progress",
        extracted_clinical_data=extracted,
    )

    record = get_patient_longitudinal_record(db_session, p.id)
    meds = record["visits"][0]["medications"]
    statuses = {m["name"]: m["status"] for m in meds}
    assert statuses["Insulin"] == "active"
    assert statuses["Metformin"] == "stopped yesterday"


# ---------------------------------------------------------------------------
# Tests: allergy provenance
# ---------------------------------------------------------------------------

def test_ai_extracted_allergy_not_labelled_doctor_reviewed_unfinalized(db_session):
    """
    For an unfinalized visit, extracted allergies must have provenance
    'ai-extracted-unverified', not any form of 'doctor-reviewed'.
    """
    from backend.app.services.record_service import get_patient_longitudinal_record

    p = _make_patient(db_session, name="Allergy Prov Unfinalized Patient")
    s = _make_session(db_session, p.id)
    _make_intake(db_session, s.id, p.id, "Allergy check")

    extracted = json.dumps({
        "symptoms": [],
        "medical_history": [],
        "medications": [],
        "allergies": [
            {"substance": "Penicillin", "reaction": "rash", "severity": "moderate"},
        ],
        "observations": [],
        "diagnoses": [],
        "plan": [],
        "negative_findings": [],
        "provenance": "ai-extracted",
    })
    _make_consultation(
        db_session, p.id, s.id,
        with_soap=False, with_final=False, status="in-progress",
        extracted_clinical_data=extracted,
    )

    record = get_patient_longitudinal_record(db_session, p.id)
    allergies = record["visits"][0]["allergies"]
    assert len(allergies) == 1
    prov = allergies[0]["provenance"]
    assert "doctor" not in prov.lower(), (
        f"Unfinalized visit allergy must not claim any doctor review; got provenance='{prov}'"
    )
    assert prov == "ai-extracted-unverified"


def test_ai_extracted_allergy_provenance_finalized_visit(db_session):
    """
    For a finalized visit, extracted allergies must still have provenance
    'ai-extracted-unverified'. Finalization of the visit does NOT imply
    individual allergens were doctor-reviewed or doctor-confirmed.
    """
    from backend.app.services.record_service import get_patient_longitudinal_record

    p = _make_patient(db_session, name="Allergy Prov Finalized Patient")
    s = _make_session(db_session, p.id)
    _make_intake(db_session, s.id, p.id, "Allergy finalized visit")

    extracted = json.dumps({
        "symptoms": [],
        "medical_history": [],
        "medications": [],
        "allergies": [
            {"substance": "Latex", "reaction": "hives", "severity": "mild"},
        ],
        "observations": [],
        "diagnoses": [],
        "plan": [],
        "negative_findings": [],
        "provenance": "ai-extracted",
    })
    _make_consultation(
        db_session, p.id, s.id,
        with_final=True, status="completed",
        extracted_clinical_data=extracted,
    )

    record = get_patient_longitudinal_record(db_session, p.id)
    allergies = record["visits"][0]["allergies"]
    assert len(allergies) == 1
    prov = allergies[0]["provenance"]

    # Must be ai-extracted-unverified — finalization does NOT confer doctor-review
    assert prov == "ai-extracted-unverified", (
        f"Allergy on a finalized visit must still be 'ai-extracted-unverified'; got '{prov}'"
    )
    # Explicit negative assertions
    assert "doctor-reviewed" not in prov.lower(), (
        f"Allergy provenance must not claim doctor-reviewed; got '{prov}'"
    )
    assert "doctor-confirmed" not in prov.lower(), (
        f"Allergy provenance must not claim doctor-confirmed; got '{prov}'"
    )


def test_nkda_not_included_as_clinical_allergy(db_session):
    """NKDA must be excluded from the allergy list in the record."""
    from backend.app.services.record_service import get_patient_longitudinal_record

    p = _make_patient(db_session, name="NKDA Patient")
    s = _make_session(db_session, p.id)
    _make_intake(db_session, s.id, p.id, "General check", allergies="NKDA")

    extracted = json.dumps({
        "symptoms": [],
        "medical_history": [],
        "medications": [],
        "allergies": [
            {"substance": "NKDA", "reaction": None, "severity": None},
            {"substance": "No known allergies", "reaction": None, "severity": None},
        ],
        "observations": [],
        "diagnoses": [],
        "plan": [],
        "negative_findings": [],
        "provenance": "ai-extracted",
    })
    _make_consultation(
        db_session, p.id, s.id,
        with_soap=False, with_final=False, status="in-progress",
        extracted_clinical_data=extracted,
    )

    record = get_patient_longitudinal_record(db_session, p.id)
    allergies = record["visits"][0]["allergies"]
    assert allergies == [], (
        f"NKDA and similar strings must not appear as clinical allergies; got {allergies}"
    )


# ---------------------------------------------------------------------------
# Tests: finalized SOAP provenance
# ---------------------------------------------------------------------------

def test_finalized_visit_with_doctor_approved_soap_labelled_correctly(db_session):
    """When final_record contains a soap field, its provenance is 'doctor-approved'."""
    from backend.app.services.record_service import get_patient_longitudinal_record

    p = _make_patient(db_session, name="Final SOAP Patient")
    s = _make_session(db_session, p.id)
    _make_intake(db_session, s.id, p.id, "Final SOAP test")
    _make_consultation(db_session, p.id, s.id, with_final=True, with_final_soap=True)

    record = get_patient_longitudinal_record(db_session, p.id)
    soap = record["visits"][0]["soap"]
    assert soap is not None
    assert soap["provenance"] == "doctor-approved", (
        f"Expected 'doctor-approved' provenance for finalized SOAP, got '{soap['provenance']}'"
    )


def test_finalized_visit_missing_final_soap_uses_draft_with_ai_label(db_session):
    """
    When a visit is finalized but final_record has no soap field,
    the SOAP draft must be used but labelled 'ai-generated-draft-unverified',
    never 'doctor-approved'.
    """
    from backend.app.services.record_service import get_patient_longitudinal_record

    p = _make_patient(db_session, name="Missing Final SOAP Patient")
    s = _make_session(db_session, p.id)
    _make_intake(db_session, s.id, p.id, "Missing final SOAP test")
    # with_final=True but with_final_soap=False → final_record exists, no soap key inside
    _make_consultation(db_session, p.id, s.id, with_final=True, with_final_soap=False, with_soap=True)

    record = get_patient_longitudinal_record(db_session, p.id)
    visit = record["visits"][0]
    assert visit["is_finalized"] is True
    soap = visit["soap"]
    assert soap is not None, "SOAP draft should be shown even when final_record has no soap"
    assert soap["provenance"] != "doctor-approved", (
        f"Draft SOAP must NOT be labelled 'doctor-approved'; got '{soap['provenance']}'"
    )
    assert "ai-generated" in soap["provenance"], (
        f"Draft SOAP must be labelled as AI-generated; got '{soap['provenance']}'"
    )


def test_unfinalized_visit_soap_draft_labelled_ai_generated(db_session):
    """SOAP draft on an in-progress visit is labelled 'ai-generated-draft-unverified'."""
    from backend.app.services.record_service import get_patient_longitudinal_record

    p = _make_patient(db_session, name="Draft SOAP Patient")
    s = _make_session(db_session, p.id)
    _make_intake(db_session, s.id, p.id, "Draft SOAP test")
    _make_consultation(db_session, p.id, s.id, with_soap=True, with_final=False, status="in-progress")

    record = get_patient_longitudinal_record(db_session, p.id)
    soap = record["visits"][0]["soap"]
    assert soap is not None
    assert soap["provenance"] == "ai-generated-draft-unverified"


# ---------------------------------------------------------------------------
# Tests: special characters and robustness
# ---------------------------------------------------------------------------

def test_special_characters_in_patient_text_do_not_crash_pdf(client, db_session):
    """
    Patient name and clinical text containing <, >, &, quotes, and Unicode
    must not break PDF generation.
    """
    p = _make_patient(
        db_session,
        name="O'Brien & Smith <Test> \"Patient\"",
        mrn="MRN-SPECIAL-01",
    )
    s = _make_session(db_session, p.id)
    _make_intake(
        db_session, s.id, p.id,
        complaint="Pain in <shoulder> & \"neck\" > 3/10",
        medications="Ibuprofen 400mg (PRN) & Paracetamol",
        allergies="Penicillin <severe> & Sulfa drugs",
    )
    extracted = json.dumps({
        "symptoms": [{"name": "Pain <shoulder> & neck > 3/10", "duration": None, "severity": None, "onset": None, "details": None}],
        "medical_history": [],
        "medications": [
            {"name": "Ibuprofen <400mg>", "dose": "400mg", "frequency": "PRN", "status": "active"},
        ],
        "allergies": [
            {"substance": "Sulfa & <drugs>", "reaction": "rash > moderate", "severity": "moderate"},
        ],
        "observations": ["BP 120/80 & HR 72"],
        "diagnoses": ["Cervicalgia <C5-C6>"],
        "plan": ["Follow up in 2 weeks & review MRI"],
        "negative_findings": [],
        "provenance": "ai-extracted",
    })
    _make_consultation(
        db_session, p.id, s.id,
        with_soap=True, with_final=True,
        extracted_clinical_data=extracted,
    )

    resp = client.get(f"/api/patients/{p.id}/record/pdf")
    assert resp.status_code == 200, (
        f"PDF generation must not crash on special characters; got {resp.status_code}: {resp.text[:300]}"
    )
    assert resp.content[:4] == b"%PDF"


def test_unicode_text_in_clinical_data_does_not_crash_pdf(client, db_session):
    """Unicode patient name and clinical notes must not crash PDF generation."""
    p = _make_patient(db_session, name="José García Müller", mrn="MRN-UNICODE-01")
    s = _make_session(db_session, p.id)
    _make_intake(
        db_session, s.id, p.id,
        complaint="Dolor de cabeza — migraña",
        medications="Ibuprofeno 600mg",
        allergies="Penicilina",
    )
    _make_consultation(db_session, p.id, s.id)

    resp = client.get(f"/api/patients/{p.id}/record/pdf")
    assert resp.status_code == 200, (
        f"PDF must not crash on Unicode; got {resp.status_code}: {resp.text[:200]}"
    )
    assert resp.content[:4] == b"%PDF"


# ---------------------------------------------------------------------------
# Tests: malformed JSON
# ---------------------------------------------------------------------------

def test_malformed_intake_conditions_json_does_not_crash_pdf(client, db_session):
    """Malformed JSON in intake.conditions must not crash PDF generation."""
    p = _make_patient(db_session, name="Bad JSON Conditions Patient")
    s = _make_session(db_session, p.id)
    # Deliberately malformed JSON in conditions column
    _make_intake(
        db_session, s.id, p.id,
        complaint="General check",
        conditions="NOT_VALID_JSON[[[",
    )
    _make_consultation(db_session, p.id, s.id)

    resp = client.get(f"/api/patients/{p.id}/record/pdf")
    assert resp.status_code == 200, (
        f"Malformed conditions JSON must not crash PDF generation; got {resp.status_code}: {resp.text[:200]}"
    )
    assert resp.content[:4] == b"%PDF"


def test_malformed_conditions_json_returns_empty_list_in_record(db_session):
    """Malformed intake.conditions JSON is silently treated as an empty list in the record dict."""
    from backend.app.services.record_service import get_patient_longitudinal_record

    p = _make_patient(db_session, name="Malformed Conds Record Patient")
    s = _make_session(db_session, p.id)
    _make_intake(
        db_session, s.id, p.id,
        complaint="Follow-up",
        conditions="{not valid json}",
    )
    _make_consultation(db_session, p.id, s.id)

    record = get_patient_longitudinal_record(db_session, p.id)
    assert isinstance(record["intake_summary"]["conditions"], list)
    assert record["intake_summary"]["conditions"] == []


# ---------------------------------------------------------------------------
# Tests: chronological ordering in get_patient_longitudinal_record
# ---------------------------------------------------------------------------

def test_longitudinal_record_visits_returned_oldest_first(db_session):
    """
    get_patient_longitudinal_record must return visits in ascending created_at order
    (oldest first / visit_number 1 before visit_number 2), regardless of the order
    rows were inserted.

    Two consultations are created with deliberately reversed created_at timestamps
    so that the second-inserted consultation is chronologically earlier.
    """
    from datetime import timedelta
    from backend.app.services.record_service import get_patient_longitudinal_record

    p = _make_patient(db_session, name="Chron Order Longitudinal Patient")
    s1 = _make_session(db_session, p.id)
    s2 = _make_session(db_session, p.id)
    _make_intake(db_session, s1.id, p.id, "Later complaint")
    _make_intake(db_session, s2.id, p.id, "Earlier complaint")

    now = _utc_now()
    # Insert the "later" consultation first with a future timestamp
    c_later = Consultation(
        id=str(uuid.uuid4()),
        patient_id=p.id,
        session_id=s1.id,
        status="completed",
        transcript="Later visit transcript.",
        finalized_at=now + timedelta(days=1),
        created_at=now + timedelta(days=1),
        updated_at=now + timedelta(days=1),
    )
    # Insert the "earlier" consultation second with a past timestamp
    c_earlier = Consultation(
        id=str(uuid.uuid4()),
        patient_id=p.id,
        session_id=s2.id,
        status="completed",
        transcript="Earlier visit transcript.",
        finalized_at=now - timedelta(days=1),
        created_at=now - timedelta(days=1),
        updated_at=now - timedelta(days=1),
    )
    db_session.add(c_later)
    db_session.add(c_earlier)
    db_session.commit()

    record = get_patient_longitudinal_record(db_session, p.id)
    assert record["total_visits"] == 2

    visits = record["visits"]
    # visit_number 1 must be the chronologically earlier consultation
    assert visits[0]["consultation_id"] == c_earlier.id, (
        f"Expected the chronologically earlier consultation as visit #1; "
        f"got {visits[0]['consultation_id']}"
    )
    assert visits[0]["visit_number"] == 1
    assert visits[1]["consultation_id"] == c_later.id, (
        f"Expected the chronologically later consultation as visit #2; "
        f"got {visits[1]['consultation_id']}"
    )
    assert visits[1]["visit_number"] == 2


# ---------------------------------------------------------------------------
# Tests: isolated visit-history regression (synthetic, no real database)
# ---------------------------------------------------------------------------

def test_two_distinct_consultations_same_patient_shown_as_separate_visits(db_session):
    """
    Regression for the Aarav Mehta visit-history inconsistency.
    Two consultation rows created for the same patient_id must appear as two
    separate items in the visit list, not merged or deduplicated.

    Uses entirely synthetic in-memory data — does not touch the real database.
    """
    p = _make_patient(db_session, name="Two Consult Regression Patient")

    # Simulate: Visit 1 — finalized, with final_record
    s1 = _make_session(db_session, p.id)
    _make_intake(db_session, s1.id, p.id, "First visit complaint")
    c1 = _make_consultation(db_session, p.id, s1.id, status="completed", with_final=True)

    # Simulate: Visit 2 — in-progress, no content (the empty follow-up scenario)
    s2 = _make_session(db_session, p.id)
    _make_intake(db_session, s2.id, p.id, "Second visit complaint")
    c2 = _make_consultation(
        db_session, p.id, s2.id,
        status="in-progress", with_soap=False, with_final=False,
    )

    from backend.app.services.record_service import get_patient_longitudinal_record
    record = get_patient_longitudinal_record(db_session, p.id)

    assert record["total_visits"] == 2, (
        f"Expected exactly 2 visits, got {record['total_visits']}"
    )

    ids_in_record = [v["consultation_id"] for v in record["visits"]]
    assert c1.id in ids_in_record, "Visit #1 consultation must appear in the record"
    assert c2.id in ids_in_record, "Visit #2 consultation must appear in the record"
    assert len(set(ids_in_record)) == 2, "Both consultation IDs must be distinct"

    # Visit 1 must be finalized
    visit1 = next(v for v in record["visits"] if v["consultation_id"] == c1.id)
    assert visit1["is_finalized"] is True, "Visit #1 must be marked as finalized"

    # Visit 2 must not be finalized (in-progress, no final_record)
    visit2 = next(v for v in record["visits"] if v["consultation_id"] == c2.id)
    assert visit2["is_finalized"] is False, "Visit #2 must not be marked as finalized"
    assert visit2["soap"] is None, "Visit #2 must have no SOAP (empty consultation)"


# ---------------------------------------------------------------------------
# Tests: medication status provenance and PDF pagination
# ---------------------------------------------------------------------------

def test_explicit_medication_status_preserved_and_missing_status_not_documented(db_session):
    """
    Ensure explicit medication statuses (e.g. 'active', 'prescribed', 'taken yesterday')
    from AI extraction are preserved verbatim, and never converted or overwritten.
    Ensure missing/null/empty status defaults strictly to 'Not documented' and is
    never inferred as 'Active'.
    """
    from backend.app.services.record_service import get_patient_longitudinal_record

    p = _make_patient(db_session, name="Med Status Verification Patient")
    s = _make_session(db_session, p.id)
    _make_intake(db_session, s.id, p.id, "Medication check")

    extracted_clinical = {
        "medications": [
            {"name": "Paracetamol", "dose": "500 mg", "frequency": "occasionally", "status": "active"},
            {"name": "Amoxicillin", "dose": "250 mg", "frequency": "three times daily", "status": "prescribed"},
            {"name": "Ibuprofen", "dose": "400 mg", "frequency": "as needed", "status": None},
            {"name": "Cetirizine", "dose": "10 mg", "frequency": "once daily", "status": ""},
        ]
    }
    c = _make_consultation(db_session, p.id, s.id, status="completed")
    c.extracted_clinical_data = json.dumps(extracted_clinical)
    db_session.commit()

    record = get_patient_longitudinal_record(db_session, p.id)
    meds = record["visits"][0]["medications"]
    assert len(meds) == 4

    # Explicit statuses must be preserved verbatim
    assert meds[0]["name"] == "Paracetamol"
    assert meds[0]["status"] == "active"

    assert meds[1]["name"] == "Amoxicillin"
    assert meds[1]["status"] == "prescribed"

    # Missing / None / empty status must strictly be "Not documented"
    assert meds[2]["name"] == "Ibuprofen"
    assert meds[2]["status"] == "Not documented"
    assert meds[2]["status"] != "Active"

    assert meds[3]["name"] == "Cetirizine"
    assert meds[3]["status"] == "Not documented"
    assert meds[3]["status"] != "Active"


def test_two_visit_record_pdf_single_page_pagination(db_session):
    """
    Ensure a 2-visit patient record (matching the Aarav Mehta consultation profile)
    renders onto a single page and does not create an unnecessary blank second page
    containing only a footer.
    """
    import re
    from backend.app.services.record_service import generate_patient_pdf

    p = _make_patient(db_session, name="Aarav Mehta Pagination Test")
    s1 = _make_session(db_session, p.id)
    _make_intake(db_session, s1.id, p.id, "Fever and sore throat")
    c1 = _make_consultation(db_session, p.id, s1.id, status="completed", with_final=True)
    c1.extracted_clinical_data = json.dumps({
        "symptoms": [{"name": "Fever"}, {"name": "Sore throat"}],
        "medications": [{"name": "Paracetamol", "dose": "500 mg", "frequency": "occasionally", "status": "active"}],
        "allergies": [],
        "diagnoses": ["Acute viral pharyngitis"],
    })

    s2 = _make_session(db_session, p.id)
    _make_intake(db_session, s2.id, p.id, "Follow-up visit")
    c2 = _make_consultation(db_session, p.id, s2.id, status="in-progress", with_soap=False, with_final=False)

    db_session.commit()

    pdf_bytes = generate_patient_pdf(db_session, p.id)
    assert pdf_bytes.startswith(b"%PDF"), "Must be a valid PDF"

    pages = len(re.findall(rb'/Type\s*/Page\b', pdf_bytes))
    assert pages == 1, (
        f"Expected 2-visit patient PDF to fit cleanly on 1 page without an empty trailing page, got {pages}"
    )
