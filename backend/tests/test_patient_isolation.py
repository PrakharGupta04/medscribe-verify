import pytest
from fastapi.testclient import TestClient


def test_new_patient_has_zero_previous_visits(client: TestClient):
    """
    1. A newly created patient starts with zero previous visits (consultations).
    """
    # Create an intake session
    s_res = client.post("/api/intake/sessions")
    assert s_res.status_code == 201
    token = s_res.json()["session_token"]

    # Submit intake for a new patient
    submit_payload = {
        "name": "Brand New Patient",
        "dob": "1990-01-01",
        "phone": "9876540101",
        "selected_complaints": ["Cough"],
        "duration": "3 days",
        "severity": 4,
        "additional_symptoms": [],
        "adaptive_answers": {},
        "conditions": [],
        "medications": "None",
        "allergies": "None",
        "additional_notes": "First time patient.",
    }
    sub_res = client.post(f"/api/intake/sessions/{token}/submit", json=submit_payload)
    assert sub_res.status_code == 200
    patient_id = sub_res.json()["patient_id"]

    # Before consultation starts, query consultations for this patient
    visits_res = client.get(f"/api/consultations/patient/{patient_id}")
    assert visits_res.status_code == 200
    visits = visits_res.json()
    assert visits == [], "New patient must have zero previous visits"


def test_patient_history_isolation_between_patients(client: TestClient):
    """
    2. Patient A's history must never appear for Patient B.
    6. Patient-specific allergies/diagnoses/prescriptions are isolated by patient/visit.
    """
    # 1. Create Patient A
    s1 = client.post("/api/intake/sessions").json()["session_token"]
    sub_a = client.post(
        f"/api/intake/sessions/{s1}/submit",
        json={
            "name": "Patient A",
            "dob": "1985-05-15",
            "phone": "9876541111",
            "selected_complaints": ["Headache"],
            "duration": "2 days",
            "severity": 7,
            "additional_symptoms": ["Nausea"],
            "adaptive_answers": {},
            "conditions": ["Migraine"],
            "medications": "Sumatriptan",
            "allergies": "Penicillin",
            "additional_notes": "Patient A has severe throbbing headache.",
        },
    ).json()
    patient_a_id = sub_a["patient_id"]

    # Start consultation for Patient A
    c_a = client.post("/api/consultations", json={"patient_id": patient_a_id, "session_id": s1}).json()
    cons_a_id = c_a["id"]

    # Update transcript and generate extraction/SOAP for Patient A
    transcript_a = (
        "Doctor: Hello Patient A. What brings you in today?\n"
        "Patient A: I have had a severe throbbing headache for 2 days with nausea. Also I am allergic to penicillin.\n"
        "Doctor: I see. Neurological exam is intact. My assessment is acute migraine. We will start oral sumatriptan 50 mg."
    )
    client.put(f"/api/consultations/{cons_a_id}/transcript", json={"transcript": transcript_a})
    ext_a = client.post(f"/api/consultations/{cons_a_id}/extract").json()
    soap_a = client.post(f"/api/consultations/{cons_a_id}/soap-draft").json()

    # 2. Create Patient B (completely separate)
    s2 = client.post("/api/intake/sessions").json()["session_token"]
    sub_b = client.post(
        f"/api/intake/sessions/{s2}/submit",
        json={
            "name": "Patient B",
            "dob": "1992-08-20",
            "phone": "9876542222",
            "selected_complaints": ["Knee Pain"],
            "duration": "1 week",
            "severity": 3,
            "additional_symptoms": [],
            "adaptive_answers": {},
            "conditions": [],
            "medications": "None",
            "allergies": "None",
            "additional_notes": "Patient B twisted knee during football.",
        },
    ).json()
    patient_b_id = sub_b["patient_id"]
    assert patient_b_id != patient_a_id

    # Check Patient B visits before starting consultation
    b_visits_before = client.get(f"/api/consultations/patient/{patient_b_id}").json()
    assert len(b_visits_before) == 0, "Patient B must start with zero visits"

    # Start consultation for Patient B
    c_b = client.post("/api/consultations", json={"patient_id": patient_b_id, "session_id": s2}).json()
    cons_b_id = c_b["id"]
    assert cons_b_id != cons_a_id

    # Check Patient B visits
    b_visits = client.get(f"/api/consultations/patient/{patient_b_id}").json()
    assert len(b_visits) == 1
    assert b_visits[0]["id"] == cons_b_id
    assert b_visits[0]["patient_id"] == patient_b_id

    # Verify Patient B visit has empty transcript, no headache, no penicillin allergy
    assert b_visits[0]["transcript"] == ""
    assert "Headache" not in (b_visits[0]["transcript"] or "")
    assert "penicillin" not in (b_visits[0]["transcript"] or "").lower()

    # Update transcript and extract for Patient B
    transcript_b = (
        "Doctor: Hello Patient B, what happened?\n"
        "Patient B: I twisted my right knee playing football. No known allergies.\n"
        "Doctor: Right knee has mild joint line tenderness. Assessment: right knee sprain. Plan: ice, rest, ibuprofen 400 mg."
    )
    client.put(f"/api/consultations/{cons_b_id}/transcript", json={"transcript": transcript_b})
    ext_b = client.post(f"/api/consultations/{cons_b_id}/extract").json()
    soap_b = client.post(f"/api/consultations/{cons_b_id}/soap-draft").json()

    # Verify clinical isolation
    # Patient A's SOAP should have Migraine, Sumatriptan, Penicillin allergy
    assert "migraine" in soap_a["soap_draft"]["assessment"].lower()
    ext_data_a = ext_a.get("extracted_clinical_data") or {}
    assert any("penicillin" in item.get("substance", "").lower() for item in ext_data_a.get("allergies", []))

    # Patient B's SOAP should have knee sprain, NOT migraine, NOT penicillin
    assert "knee" in soap_b["soap_draft"]["assessment"].lower()
    assert "migraine" not in soap_b["soap_draft"]["assessment"].lower()
    assert "penicillin" not in soap_b["soap_draft"]["subjective"].lower()
    assert "penicillin" not in soap_b["soap_draft"]["assessment"].lower()
    ext_data_b = ext_b.get("extracted_clinical_data") or {}
    assert not any("penicillin" in item.get("substance", "").lower() for item in ext_data_b.get("allergies", []))


def test_patient_can_have_multiple_visits_independently(client: TestClient):
    """
    3. Patient A can have multiple visits.
    4. Visit 1 and Visit 2 retain independent consultation/transcript/extraction/SOAP data.
    5. Visit History returns only visits belonging to the selected patient.
    """
    # 1. Create Patient A intake
    s1 = client.post("/api/intake/sessions").json()["session_token"]
    sub1 = client.post(
        f"/api/intake/sessions/{s1}/submit",
        json={
            "name": "Returning Patient",
            "dob": "1988-12-05",
            "phone": "9876548888",
            "selected_complaints": ["Headache"],
            "duration": "1 day",
            "severity": 6,
            "additional_symptoms": [],
            "adaptive_answers": {},
            "conditions": [],
            "medications": "None",
            "allergies": "None",
            "additional_notes": "Visit 1: acute headache.",
        },
    ).json()
    patient_id = sub1["patient_id"]
    mrn = sub1["mrn"]

    # 2. Visit 1: Start consultation
    c1 = client.post("/api/consultations", json={"patient_id": patient_id, "session_id": s1}).json()
    v1_id = c1["id"]
    transcript_v1 = (
        "Doctor: Hello, how is your headache?\n"
        "Patient: Severe headache on forehead.\n"
        "Doctor: Assessment is tension headache. Plan is acetaminophen 500 mg."
    )
    client.put(f"/api/consultations/{v1_id}/transcript", json={"transcript": transcript_v1})
    client.post(f"/api/consultations/{v1_id}/extract")
    soap_v1 = client.post(f"/api/consultations/{v1_id}/soap-draft").json()

    # Complete Visit 1
    comp_res = client.post(f"/api/consultations/{v1_id}/complete")
    assert comp_res.status_code == 200
    assert comp_res.json()["status"] == "completed"

    # 3. Returning patient intake: submitting with existing patient_id or mrn
    s2 = client.post("/api/intake/sessions").json()["session_token"]
    sub2 = client.post(
        f"/api/intake/sessions/{s2}/submit",
        json={
            "patient_id": patient_id,
            "mrn": mrn,
            "name": "Returning Patient",
            "dob": "1988-12-05",
            "phone": "9876548888",
            "selected_complaints": ["Rash"],
            "duration": "3 days",
            "severity": 4,
            "additional_symptoms": ["Itching"],
            "adaptive_answers": {},
            "conditions": [],
            "medications": "None",
            "allergies": "None",
            "additional_notes": "Visit 2: erythematous rash on left arm.",
        },
    ).json()

    # Must reuse the same patient entity
    assert sub2["patient_id"] == patient_id
    assert sub2["mrn"] == mrn

    # 4. Visit 2: Start new consultation (force_new=True)
    c2 = client.post(
        "/api/consultations",
        json={"patient_id": patient_id, "session_id": s2, "force_new": True},
    ).json()
    v2_id = c2["id"]
    assert v2_id != v1_id

    transcript_v2 = (
        "Doctor: Welcome back. I see you now have a rash.\n"
        "Patient: Yes, an itchy rash on my left arm for 3 days.\n"
        "Doctor: Exam shows erythematous macular rash without wheals. Assessment is contact dermatitis. Plan: topical hydrocortisone 1% cream."
    )
    client.put(f"/api/consultations/{v2_id}/transcript", json={"transcript": transcript_v2})
    client.post(f"/api/consultations/{v2_id}/extract")
    soap_v2 = client.post(f"/api/consultations/{v2_id}/soap-draft").json()

    # 5. Query visits list for this patient
    visits_res = client.get(f"/api/consultations/patient/{patient_id}")
    assert visits_res.status_code == 200
    visits = visits_res.json()
    assert len(visits) == 2

    visit_ids = [v["id"] for v in visits]
    assert v1_id in visit_ids
    assert v2_id in visit_ids

    # 6. Verify independent data retention
    # Visit 1 check
    get_v1 = client.get(f"/api/consultations/{v1_id}").json()
    assert get_v1["transcript"] == transcript_v1
    assert "tension headache" in soap_v1["soap_draft"]["assessment"].lower()
    assert "contact dermatitis" not in soap_v1["soap_draft"]["assessment"].lower()

    # Visit 2 check
    get_v2 = client.get(f"/api/consultations/{v2_id}").json()
    assert get_v2["transcript"] == transcript_v2
    assert "contact dermatitis" in soap_v2["soap_draft"]["assessment"].lower()
    assert "tension headache" not in soap_v2["soap_draft"]["assessment"].lower()


def test_new_patient_does_not_inherit_demo_history(client: TestClient):
    """
    7. A new patient cannot inherit demo/seed historical records.
    Historical URTI, penicillin hypersensitivity, acute pharyngitis must never appear.
    """
    s = client.post("/api/intake/sessions").json()["session_token"]
    sub = client.post(
        f"/api/intake/sessions/{s}/submit",
        json={
            "name": "SOAP Test Patient",
            "dob": "1995-02-14",
            "phone": "9876547777",
            "selected_complaints": ["Sore throat"],
            "duration": "2 days",
            "severity": 5,
            "additional_symptoms": [],
            "adaptive_answers": {},
            "conditions": [],
            "medications": "None",
            "allergies": "None",
            "additional_notes": "No previous medical history.",
        },
    ).json()
    patient_id = sub["patient_id"]

    # Retrieve patient's consultation visits
    visits = client.get(f"/api/consultations/patient/{patient_id}").json()
    assert visits == [], "New patient should have 0 visits prior to starting one"

    # Start consultation
    c = client.post("/api/consultations", json={"patient_id": patient_id, "session_id": s}).json()
    cons_id = c["id"]

    # Verify fresh consultation has empty transcript and no historical data
    assert c["transcript"] == ""
    assert c["soap_draft"] is None

    # Retrieve visits list again
    visits_after = client.get(f"/api/consultations/patient/{patient_id}").json()
    assert len(visits_after) == 1
    v = visits_after[0]
    assert v["id"] == cons_id

    # Ensure none of the hardcoded demo strings appear in the consultation record
    consultation_str = str(v).lower()
    forbidden_historical_strings = [
        "upper respiratory tract infection",
        "penicillin hypersensitivity reaction",
        "acute pharyngitis — group a streptococcus",
        "amoxicillin 500mg",
    ]
    for forbidden in forbidden_historical_strings:
        assert forbidden not in consultation_str, f"Found leaked demo history: {forbidden}"
