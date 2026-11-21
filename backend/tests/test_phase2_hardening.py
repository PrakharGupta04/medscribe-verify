from fastapi.testclient import TestClient

from backend.app.db.models import Consultation
from backend.app.schemas.consultation import (
    ClinicalExtraction, ComparisonItem, ComparisonResults, ExtractedAllergy, SoapDraft,
)
from backend.app.services.consultation_service import (
    _carry_over_resolutions,
    compare_consultation,
    resolve_discrepancy,
)
from backend.app.services.verification_service import verify_soap_claims


def _item(item_id, label, type_, status="unresolved", resolution=None, intake_val="i", consult_val="c"):
    return ComparisonItem(
        id=item_id, category="allergies", type=type_, label=label,
        intake_value=intake_val, consultation_value=consult_val, description="d",
        status=status, resolution=resolution,
    )


def test_verification_scattered_words_are_not_supported():
    transcript = (
        "Patient: I have a headache.\n"
        "Doctor: Take plenty of rest in the evening.\n"
        "Patient: It began yesterday."
    )
    soap = SoapDraft(
        subjective="Patient reports severe headache lasting yesterday evening.",
        objective="Not documented.",
        assessment="Not explicitly documented.",
        plan="Not documented.",
    )
    results = verify_soap_claims(transcript, ClinicalExtraction(), soap)
    sub = [c for c in results.claims if c.section == "subjective"]
    assert len(sub) == 1
    assert sub[0].status == "unsupported"


def test_carry_over_resolutions_preserves_only_resolved_matches():
    old = ComparisonResults(items=[
        _item("comp-alg-1", "Allergy Disclosure", "discrepancy", "resolved", "Confirmed with patient"),
        _item("comp-alg-2", "Other Finding", "discrepancy"),
    ])
    new = ComparisonResults(items=[
        _item("comp-alg-7", "Allergy Disclosure", "discrepancy"),
        _item("comp-alg-8", "Other Finding", "discrepancy"),
        _item("comp-alg-9", "Brand New", "discrepancy"),
    ])
    out = _carry_over_resolutions(old, new)
    by_label = {i.label: i for i in out.items}
    assert by_label["Allergy Disclosure"].status == "resolved"
    assert by_label["Allergy Disclosure"].resolution == "Confirmed with patient"
    assert by_label["Other Finding"].status == "unresolved"
    assert by_label["Other Finding"].resolution is None
    assert by_label["Brand New"].resolution is None


def test_carry_over_with_no_previous_results_returns_new_untouched():
    new = ComparisonResults(items=[_item("comp-alg-1", "X", "discrepancy")])
    out = _carry_over_resolutions(None, new)
    assert out.items[0].resolution is None
    assert out.items[0].status == "unresolved"


def test_carry_over_resolutions_invalidated_by_underlying_value_changes():
    """
    Confirms:
    1. An unchanged discrepancy retains its doctor resolution.
    2. A discrepancy with the same category, label, and type but changed underlying
       values does NOT inherit the old resolution.
    """
    old = ComparisonResults(items=[
        _item(
            "comp-1", "Duration", "discrepancy",
            status="resolved", resolution="Doctor confirmed 3 days",
            intake_val="2 days", consult_val="4 days",
        ),
        _item(
            "comp-2", "Allergy", "discrepancy",
            status="resolved", resolution="Confirmed penicillin allergy",
            intake_val="None reported", consult_val="Penicillin",
        ),
    ])
    new = ComparisonResults(items=[
        # 1. Unchanged discrepancy: retains resolution
        _item(
            "comp-7", "Allergy", "discrepancy",
            intake_val="None reported", consult_val="Penicillin",
        ),
        # 2. Same category, label, and type, but changed consultation value (now 7 days): does NOT inherit
        _item(
            "comp-8", "Duration", "discrepancy",
            intake_val="2 days", consult_val="7 days",
        ),
        # 3. Same category, label, and type, but changed intake value: does NOT inherit
        _item(
            "comp-9", "Allergy", "discrepancy",
            intake_val="Latex", consult_val="Penicillin",
        ),
    ])
    out = _carry_over_resolutions(old, new)
    by_key = {f"{i.label}_{i.intake_value}_{i.consultation_value}": i for i in out.items}

    # 1. Unchanged retains doctor's resolution
    assert by_key["Allergy_None reported_Penicillin"].status == "resolved"
    assert by_key["Allergy_None reported_Penicillin"].resolution == "Confirmed penicillin allergy"

    # 2. Changed consultation_value does NOT inherit
    assert by_key["Duration_2 days_7 days"].status == "unresolved"
    assert by_key["Duration_2 days_7 days"].resolution is None

    # 3. Changed intake_value does NOT inherit
    assert by_key["Allergy_Latex_Penicillin"].status == "unresolved"
    assert by_key["Allergy_Latex_Penicillin"].resolution is None


def test_compare_consultation_preserves_resolutions_on_regeneration(client: TestClient, db_session):
    """
    Integration test for compare_consultation():
    Confirms that a doctor's existing resolution survives regeneration
    when the matching comparison item remains present.
    """
    # 1. Create intake session and submit intake
    token = client.post("/api/intake/sessions").json()["session_token"]
    sub_res = client.post(
        f"/api/intake/sessions/{token}/submit",
        json={
            "name": "Integration Test Patient",
            "dob": "1990-01-01",
            "phone": "9876540101",
            "selected_complaints": ["Fever"],
            "duration": "3 days",
            "severity": 4,
            "additional_symptoms": [],
            "conditions": [],
            "medications": "None reported",
            "allergies": "No known drug allergies",
        },
    )
    assert sub_res.status_code == 200
    patient_id = sub_res.json()["patient_id"]

    # 2. Create consultation
    c_res = client.post("/api/consultations", json={"patient_id": patient_id, "session_id": token})
    assert c_res.status_code == 201
    consultation_id = c_res.json()["id"]

    # 3. Attach clinical extraction with Penicillin allergy (discrepancy with intake)
    extraction = ClinicalExtraction(
        allergies=[ExtractedAllergy(substance="Penicillin", reaction="skin rash")],
    )
    consultation = db_session.query(Consultation).filter(Consultation.id == consultation_id).first()
    consultation.extracted_clinical_data = extraction.model_dump_json()
    db_session.commit()

    # 4. Initial comparison produces allergy discrepancy
    c1 = compare_consultation(db_session, consultation_id)
    res1 = ComparisonResults.model_validate_json(c1.comparison_results)
    allergy_items = [i for i in res1.items if i.category == "allergies"]
    assert len(allergy_items) >= 1
    target_item = allergy_items[0]
    assert target_item.status == "unresolved"
    assert target_item.resolution is None

    # 5. Doctor resolves the discrepancy
    doctor_note = "Doctor confirmed penicillin rash occurred in childhood. Chart updated."
    c_resolved = resolve_discrepancy(
        db_session,
        consultation_id=consultation_id,
        item_id=target_item.id,
        resolution=doctor_note,
    )
    res_resolved = ComparisonResults.model_validate_json(c_resolved.comparison_results)
    resolved_item = next(i for i in res_resolved.items if i.id == target_item.id)
    assert resolved_item.status == "resolved"
    assert resolved_item.resolution == doctor_note

    # 6. Doctor regenerates / re-runs compare_consultation()
    c2 = compare_consultation(db_session, consultation_id)
    res2 = ComparisonResults.model_validate_json(c2.comparison_results)

    # 7. Confirm resolution survived regeneration on the matching item
    surviving = next(
        i for i in res2.items
        if (i.category, i.label, i.type) == (target_item.category, target_item.label, target_item.type)
    )
    assert surviving.status == "resolved"
    assert surviving.resolution == doctor_note

