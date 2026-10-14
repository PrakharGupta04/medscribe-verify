import pytest
from fastapi.testclient import TestClient

from backend.app.schemas.consultation import (
    ClinicalExtraction,
    ExtractedSymptom,
    ExtractedMedication,
    ExtractedAllergy,
    SoapDraft,
)
from backend.app.services.verification_service import verify_soap_claims
from backend.app.services.comparison_service import compare_intake_and_consultation


def test_verification_agent_unit():
    """Unit test for Agent 3: Verification Agent with claim-level provenance and absence checks."""
    transcript = (
        "Doctor: How long have you had this fever?\n"
        "Patient: About three days with mild headache. I took paracetamol 500mg twice yesterday.\n"
        "Patient: I am allergic to penicillin, it gives me a red skin rash.\n"
        "Doctor: Any chest pain or difficulty breathing?\n"
        "Patient: No chest pain at all.\n"
        "Doctor: I have examined you and diagnosed acute viral pharyngitis. Take rest, hydrate, and continue paracetamol."
    )

    extraction = ClinicalExtraction(
        symptoms=[
            ExtractedSymptom(name="Fever", duration="3 days"),
            ExtractedSymptom(name="Headache", severity="mild"),
        ],
        medications=[ExtractedMedication(name="Paracetamol", dose="500mg", frequency="twice yesterday")],
        allergies=[ExtractedAllergy(substance="Penicillin", reaction="red skin rash")],
        negative_findings=["No chest pain"],
        diagnoses=["Acute viral pharyngitis"],
        plan=["Take rest", "Hydrate", "Continue paracetamol"],
    )

    # 1. Conservative, supported SOAP draft
    good_soap = SoapDraft(
        subjective="Patient reports fever for 3 days and mild headache. Reports taking paracetamol. Penicillin allergy with red skin rash. Denies chest pain.",
        objective="Not documented.",
        assessment="Acute viral pharyngitis stated by clinician.",
        plan="Hydration, rest, and continue paracetamol.",
    )

    results = verify_soap_claims(transcript, extraction, good_soap)
    assert results.total_claims >= 4
    assert results.unsupported_count == 0
    assert results.supported_count >= 4

    # Verify absence check on Objective section
    obj_claim = next((c for c in results.claims if c.section == "objective"), None)
    assert obj_claim is not None
    assert obj_claim.status == "supported"
    assert "Absence confirmed" in obj_claim.evidence

    # 2. Hallucinated / Unsupported SOAP draft
    bad_soap = SoapDraft(
        subjective="Patient has severe nausea and vomiting for 2 weeks.",
        objective="Blood pressure 120/80 mmHg, pulse 72 bpm, lungs clear to auscultation.",
        assessment="Severe bacterial pneumonia.",
        plan="Prescribe amoxicillin 875mg orally BID for 10 days.",
    )

    bad_results = verify_soap_claims(transcript, extraction, bad_soap)
    # Objective has ungrounded vitals -> must be unsupported
    bad_obj_claims = [c for c in bad_results.claims if c.section == "objective"]
    assert any(c.status == "unsupported" for c in bad_obj_claims)

    # Assessment has ungrounded diagnosis (pneumonia vs pharyngitis) -> must be unsupported
    bad_ass_claims = [c for c in bad_results.claims if c.section == "assessment"]
    assert any(c.status == "unsupported" for c in bad_ass_claims)

    # Plan has ungrounded prescription (amoxicillin for penicillin allergic patient!) -> must be unsupported
    bad_plan_claims = [c for c in bad_results.claims if c.section == "plan"]
    assert any(c.status == "unsupported" for c in bad_plan_claims)


def test_end_to_end_agentic_consultation_workflow(client: TestClient):
    """
    End-to-end integration test verifying the complete Module 2 Agentic pipeline:
    Intake -> Consultation -> Transcript -> Extraction (Agent 1) -> SOAP Draft (Agent 2)
    -> Verification (Agent 3) -> Comparison (Agent 4) -> Resolve -> Doctor Finalization.
    """
    # 1. Module 1: Patient Intake with specific details
    s_res = client.post("/api/intake/sessions")
    assert s_res.status_code == 201
    token = s_res.json()["session_token"]

    intake_payload = {
        "name": "E2E Agentic Test Patient",
        "dob": "1988-11-05",
        "phone": "9876548888",
        "selected_complaints": ["Fever"],
        "duration": "2 days",
        "severity": 6,
        "additional_symptoms": ["cough"],
        "conditions": ["None of the above"],
        "medications": "None reported",
        "allergies": "No known allergies",
        "additional_notes": "Mild body ache.",
    }
    sub_res = client.post(f"/api/intake/sessions/{token}/submit", json=intake_payload)
    assert sub_res.status_code == 200
    patient_id = sub_res.json()["patient_id"]

    # 2. Start Consultation
    c_res = client.post("/api/consultations", json={"patient_id": patient_id, "session_id": token})
    assert c_res.status_code == 201
    consultation_id = c_res.json()["id"]

    # 3. Enter Transcript (with intentional discrepancies from intake to test Agent 4)
    # Intake said: 2 days, no meds, no allergies.
    # Patient now says: 4 days, taking paracetamol, allergic to penicillin!
    transcript_text = (
        "Doctor: How long have you had this fever?\n"
        "Patient: It's actually been about 4 days now, getting worse at night.\n"
        "Doctor: Are you taking anything for it?\n"
        "Patient: I started taking paracetamol twice daily yesterday.\n"
        "Doctor: Any drug allergies?\n"
        "Patient: Yes, I forgot to mention earlier, I had a bad rash from penicillin as a child.\n"
        "Doctor: Understood. Your chest sounds clear. I diagnose you with acute upper respiratory viral infection.\n"
        "Doctor: Plan is to rest, drink fluids, and continue paracetamol as needed."
    )
    t_res = client.put(f"/api/consultations/{consultation_id}/transcript", json={"transcript": transcript_text})
    assert t_res.status_code == 200

    # 4. Agent 1: Clinical Extraction
    ext_res = client.post(f"/api/consultations/{consultation_id}/extract")
    assert ext_res.status_code == 200
    assert ext_res.json()["extracted_clinical_data"] is not None

    # 5. Agent 2: SOAP Draft Generation
    soap_res = client.post(f"/api/consultations/{consultation_id}/soap-draft")
    assert soap_res.status_code == 200
    soap_data = soap_res.json()["soap_draft"]
    assert soap_data is not None
    assert soap_data["provenance"] == "ai-generated-draft-unverified"

    # 6. Agent 3: Claim-Level Verification
    verif_res = client.post(f"/api/consultations/{consultation_id}/verify")
    assert verif_res.status_code == 200
    verif_data = verif_res.json()["verification_results"]
    assert verif_data is not None
    assert verif_data["total_claims"] > 0
    assert verif_data["provenance"] == "ai-verified"
    assert any(c["status"] == "supported" for c in verif_data["claims"])

    # 7. Agent 4: Module 1 vs Module 2 Comparison
    comp_res = client.post(f"/api/consultations/{consultation_id}/compare")
    assert comp_res.status_code == 200
    comp_data = comp_res.json()["comparison_results"]
    assert comp_data is not None
    assert comp_data["total_items"] > 0

    # Discrepancy checks:
    # - Medication: intake reported none, consult reported paracetamol
    # - Allergy: intake reported no known allergies, consult reported penicillin allergy
    discrepancies = [item for item in comp_data["items"] if item["type"] == "discrepancy"]
    assert len(discrepancies) >= 1
    target_discrepancy = discrepancies[0]

    # 8. Doctor Discrepancy Resolution
    res_payload = {"resolution": "Doctor confirmed penicillin allergy with patient. Marked active in chart."}
    resolve_res = client.put(
        f"/api/consultations/{consultation_id}/discrepancies/{target_discrepancy['id']}/resolve",
        json=res_payload,
    )
    assert resolve_res.status_code == 200
    resolved_comp = resolve_res.json()["comparison_results"]
    resolved_item = next(i for i in resolved_comp["items"] if i["id"] == target_discrepancy["id"])
    assert resolved_item["status"] == "resolved"
    assert resolved_item["resolution"] == res_payload["resolution"]

    # 9. Doctor Finalization and Medical Record Approval
    final_payload = {
        "subjective": "Patient reports fever for 4 days and body ache. Taking paracetamol. Penicillin allergy confirmed.",
        "objective": "Lungs clear to auscultation. No acute distress.",
        "assessment": "Acute upper respiratory viral infection.",
        "plan": "Hydration, rest, paracetamol PRN.",
        "doctor_notes": "Patient advised to return if fever persists beyond 7 days.",
        "doctor_name": "Dr. J. Patel",
    }
    fin_res = client.post(f"/api/consultations/{consultation_id}/finalize", json=final_payload)
    assert fin_res.status_code == 200
    fin_data = fin_res.json()

    assert fin_data["status"] == "completed"
    assert fin_data["finalized_at"] is not None
    final_record = fin_data["final_record"]
    assert final_record is not None
    assert final_record["status"] == "doctor-approved"
    assert final_record["doctor_name"] == "Dr. J. Patel"
    assert final_record["soap"]["subjective"] == final_payload["subjective"]
    assert final_record["provenance"] == "doctor-approved-final-record"

    # 10. Persistence verification: fetch record again to ensure it survives reload
    get_res = client.get(f"/api/consultations/{consultation_id}")
    assert get_res.status_code == 200
    assert get_res.json()["final_record"]["status"] == "doctor-approved"
    assert get_res.json()["finalized_at"] is not None


def test_agent4_discrete_symptom_comparison_regression(client: TestClient, db_session):
    """
    Regression test for Agent 4 comparison intelligence:
    - Module 1: Fever + Sore Throat + Difficulty swallowing + Runny nose + Chills; duration 3–5 days; no medications.
    - Module 2: Fever + Headache for 3 days; Paracetamol twice daily; Penicillin allergy with rash; no vomiting.
    Asserts:
      1. Fever is confirmed
      2. Sore Throat is not_mentioned_in_consultation
      3. Difficulty swallowing, Runny nose, Chills are not_mentioned_in_consultation
      4. Headache is new_in_consultation
      5. Paracetamol is new_in_consultation
      6. Penicillin allergy is surfaced as discrepancy / potential discrepancy
      7. No automatic comparison item contains a doctor resolution
      8. Doctor resolution workflow works cleanly when explicitly submitted
    """
    from backend.app.schemas.consultation import (
        ClinicalExtraction,
        ExtractedAllergy,
        ExtractedMedication,
        ExtractedSymptom,
    )
    from backend.app.services.comparison_service import compare_intake_and_consultation
    from backend.app.db.models import IntakeData, Consultation

    # 1. Direct unit verification of compare_intake_and_consultation
    intake_data = IntakeData(
        patient_id="test-p1",
        session_id="test-s1",
        chief_complaint="Fever, Sore Throat",
        symptoms='["Fever", "Sore Throat", "Difficulty swallowing", "Runny nose", "Chills"]',
        duration="3–5 days",
        severity=6,
        medications="no medications",
        allergies="no known allergies",
        conditions='["None of the above"]',
        additional_notes="Flu like illness",
    )

    consultation = Consultation(
        id="test-c1",
        patient_id="test-p1",
        session_id="test-s1",
        status="in-progress",
        transcript=(
            "Doctor: Hello, tell me what happened?\n"
            "Patient: I have had fever and headache for 3 days. I take paracetamol twice daily. "
            "I also have a penicillin allergy with rash. No vomiting.\n"
            "Doctor: Understood. Throat exam is normal. Plan is supportive care."
        ),
    )

    clinical_extraction = ClinicalExtraction(
        symptoms=[
            ExtractedSymptom(name="Fever", duration="3 days"),
            ExtractedSymptom(name="Headache", duration="3 days"),
        ],
        medications=[
            ExtractedMedication(name="Paracetamol", frequency="twice daily"),
        ],
        allergies=[
            ExtractedAllergy(substance="Penicillin", reaction="rash"),
        ],
        negative_findings=["vomiting"],
    )

    results = compare_intake_and_consultation(intake_data, consultation, clinical_extraction)

    # 1. Assert Fever is confirmed
    fever_items = [it for it in results.items if "fever" in it.label.lower()]
    assert len(fever_items) == 1, f"Expected 1 fever item, found {len(fever_items)}"
    assert fever_items[0].type == "confirmed", f"Fever should be confirmed, got {fever_items[0].type}"

    # 2. Assert Sore Throat is not mentioned in consultation
    st_items = [it for it in results.items if "sore throat" in it.label.lower()]
    assert len(st_items) == 1, f"Expected 1 sore throat item, found {len(st_items)}"
    assert st_items[0].type == "not_mentioned_in_consultation"

    # 3. Assert Difficulty swallowing, Runny nose, Chills are not mentioned in consultation
    diff_items = [it for it in results.items if "swallowing" in it.label.lower()]
    assert len(diff_items) == 1
    assert diff_items[0].type == "not_mentioned_in_consultation"

    runny_items = [it for it in results.items if "runny nose" in it.label.lower()]
    assert len(runny_items) == 1
    assert runny_items[0].type == "not_mentioned_in_consultation"

    chills_items = [it for it in results.items if "chills" in it.label.lower()]
    assert len(chills_items) == 1
    assert chills_items[0].type == "not_mentioned_in_consultation"

    # 4. Assert Headache is new in consultation
    headache_items = [it for it in results.items if "headache" in it.label.lower() or "headache" in (it.consultation_value or "").lower()]
    assert len(headache_items) == 1
    assert headache_items[0].type == "new_in_consultation"

    # 5. Assert Paracetamol is new in consultation
    paracetamol_items = [it for it in results.items if "paracetamol" in it.label.lower() or "paracetamol" in (it.consultation_value or "").lower()]
    assert len(paracetamol_items) == 1
    assert paracetamol_items[0].type == "new_in_consultation"

    # 6. Assert Penicillin allergy is surfaced as discrepancy / potential discrepancy
    allergy_items = [it for it in results.items if "allergy" in it.label.lower() or "penicillin" in (it.consultation_value or "").lower()]
    assert len(allergy_items) >= 1
    assert any(it.type == "discrepancy" for it in allergy_items)

    # 7. Assert that no automatic comparison item contains a doctor resolution
    assert all(it.resolution is None for it in results.items), (
        "No automatic comparison item should have a doctor resolution set!"
    )

    # 8. Test via API endpoint and verify discrepancy resolution flow
    # Submit intake
    s_res = client.post("/api/intake/sessions")
    assert s_res.status_code == 201
    token = s_res.json()["session_token"]

    intake_payload = {
        "name": "Agent4 Regression Patient",
        "dob": "1994-04-12",
        "phone": "9876544321",
        "selected_complaints": ["Fever", "Sore Throat"],
        "duration": "3–5 days",
        "severity": 6,
        "additional_symptoms": ["Difficulty swallowing", "Runny nose", "Chills"],
        "conditions": ["None of the above"],
        "medications": "no medications",
        "allergies": "no known allergies",
        "additional_notes": "Sore throat and fever",
    }
    sub_res = client.post(f"/api/intake/sessions/{token}/submit", json=intake_payload)
    assert sub_res.status_code == 200
    patient_id = sub_res.json()["patient_id"]

    # Start consultation
    c_res = client.post("/api/consultations", json={"patient_id": patient_id, "session_id": token, "force_new": True})
    assert c_res.status_code == 201
    c_id = c_res.json()["id"]

    # Save transcript
    transcript_text = (
        "Doctor: Hello, what brings you in?\n"
        "Patient: I have had fever and headache for 3 days. I take paracetamol twice daily. "
        "Also I had a penicillin allergy with rash. No vomiting.\n"
        "Doctor: Throat is clear. Plan is supportive care."
    )
    client.put(f"/api/consultations/{c_id}/transcript", json={"transcript": transcript_text})

    # Save clinical extraction directly in consultation record via db_session
    db_cons = db_session.query(Consultation).filter(Consultation.id == c_id).first()
    assert db_cons is not None
    db_cons.extracted_clinical_data = clinical_extraction.model_dump_json()
    db_session.commit()

    # Call compare API
    comp_res = client.post(f"/api/consultations/{c_id}/compare")
    assert comp_res.status_code == 200
    comp_data = comp_res.json()["comparison_results"]

    # Assert no automatic resolutions exist
    assert all(it.get("resolution") is None for it in comp_data["items"])

    # Discrepancy resolution: resolve the allergy discrepancy
    discrepancy_item = next(it for it in comp_data["items"] if it["type"] == "discrepancy")
    resolve_res = client.put(
        f"/api/consultations/{c_id}/discrepancies/{discrepancy_item['id']}/resolve",
        json={"resolution": "Patient confirmed childhood penicillin allergy with urticaria. Added to allergy alert list."},
    )
    assert resolve_res.status_code == 200
    updated_comp = resolve_res.json()["comparison_results"]
    resolved_item = next(it for it in updated_comp["items"] if it["id"] == discrepancy_item["id"])
    assert resolved_item["status"] == "resolved"
    assert resolved_item["resolution"] == "Patient confirmed childhood penicillin allergy with urticaria. Added to allergy alert list."

    # Other non-discrepancy items must STILL have resolution as None
    other_items = [it for it in updated_comp["items"] if it["id"] != discrepancy_item["id"]]
    assert all(it.get("resolution") is None for it in other_items)


def test_verification_agent_negative_finding_raw_transcript_grounding():
    """Verifies that discrete negative claims (e.g. 'Denies vomiting') ground to raw transcript statements."""
    transcript = (
        "Doctor: Hello Aarav, what brings you in today?\n"
        "Patient: I have fever and headache for three days.\n"
        "Doctor: Are you taking anything for it?\n"
        "Patient: I am taking paracetamol twice a day.\n"
        "Doctor: Any nausea or vomiting?\n"
        "Patient: I do not have vomiting.\n"
        "Doctor: Do you have any allergies?\n"
        "Patient: I am allergic to penicillin and it causes a rash."
    )

    extraction = ClinicalExtraction(
        symptoms=[
            ExtractedSymptom(name="Fever", duration="3 days"),
            ExtractedSymptom(name="Headache", duration="3 days"),
        ],
        medications=[ExtractedMedication(name="Paracetamol", frequency="twice a day")],
        allergies=[ExtractedAllergy(substance="Penicillin", reaction="rash")],
        negative_findings=["vomiting"],
        diagnoses=[],
        plan=[],
    )

    soap = SoapDraft(
        subjective="Patient reports fever and headache for three days. Taking paracetamol twice a day. Penicillin causes rash. Denies vomiting.",
        objective="Not documented.",
        assessment="Not explicitly documented.",
        plan="Not documented.",
    )

    results = verify_soap_claims(transcript, extraction, soap)
    assert results.unsupported_count == 0

    vomiting_claim = next((c for c in results.claims if "vomiting" in c.claim.lower()), None)
    assert vomiting_claim is not None
    assert vomiting_claim.status == "supported"
    assert vomiting_claim.source == "consultation-transcript"
    assert "I do not have vomiting." in vomiting_claim.evidence


