from datetime import datetime, timedelta, timezone
from backend.app.db.models import IntakeSession


def test_create_session(client):
    response = client.post("/api/intake/sessions")
    assert response.status_code == 201
    data = response.json()
    assert "session_token" in data
    assert len(data["session_token"]) > 20
    assert data["status"] == "draft"
    assert "expires_at" in data


def test_get_and_save_draft(client):
    # 1. Create session
    create_res = client.post("/api/intake/sessions")
    token = create_res.json()["session_token"]

    # 2. Get initial session
    get_res = client.get(f"/api/intake/sessions/{token}")
    assert get_res.status_code == 200
    assert get_res.json()["status"] == "draft"

    # 3. Save partial draft
    draft_payload = {
        "name": "Jane Doe",
        "dob": "1995-04-12",
        "phone": "+44 7700 900111",
        "selected_complaints": ["Fever"],
        "duration": "3–5 days",
        "severity": 7,
    }
    save_res = client.put(f"/api/intake/sessions/{token}", json=draft_payload)
    assert save_res.status_code == 200
    data = save_res.json()
    assert data["draft_data"]["name"] == "Jane Doe"
    assert data["draft_data"]["severity"] == 7
    assert data["draft_data"]["selected_complaints"] == ["Fever"]


def test_validation_errors_on_submit(client):
    create_res = client.post("/api/intake/sessions")
    token = create_res.json()["session_token"]

    # Missing name
    res = client.post(
        f"/api/intake/sessions/{token}/submit",
        json={
            "name": "",
            "selected_complaints": ["Fever"],
            "duration": "1–2 days",
            "severity": 5,
        },
    )
    assert res.status_code == 422

    # Empty complaints
    res2 = client.post(
        f"/api/intake/sessions/{token}/submit",
        json={
            "name": "Valid Name",
            "selected_complaints": [],
            "duration": "1–2 days",
            "severity": 5,
        },
    )
    assert res2.status_code == 422

    # Invalid severity (< 1 or > 10)
    res3 = client.post(
        f"/api/intake/sessions/{token}/submit",
        json={
            "name": "Valid Name",
            "selected_complaints": ["Cough"],
            "duration": "1–2 days",
            "severity": 15,
        },
    )
    assert res3.status_code == 422


def test_successful_submit_and_duplicate_protection(client):
    create_res = client.post("/api/intake/sessions")
    token = create_res.json()["session_token"]

    payload = {
        "name": "Alex Smith",
        "dob": "1990-01-01",
        "phone": "9876543210",
        "selected_complaints": ["Fever", "Sore Throat"],
        "duration": "3–5 days",
        "severity": 6,
        "additional_symptoms": ["diff_swallow", "chills"],
        "adaptive_answers": {"Fever-0": "Gradually"},
        "conditions": ["None of the above"],
        "medications": "None",
        "allergies": "Penicillin — mild rash",
        "additional_notes": "Getting worse at night.",
    }

    submit_res = client.post(f"/api/intake/sessions/{token}/submit", json=payload)
    assert submit_res.status_code == 200
    data = submit_res.json()

    assert data["patient_name"] == "Alex Smith"
    assert data["mrn"].startswith("MRN-2026-")
    assert data["queue_position"] == 1
    assert data["wait_time_minutes"] == 10
    assert data["summary"]["provenance"] == "patient-reported"
    assert "Fever" in data["summary"]["chief_complaint"]

    # Duplicate submission protection
    dup_res = client.post(f"/api/intake/sessions/{token}/submit", json=payload)
    assert dup_res.status_code == 400
    assert "already been submitted" in dup_res.json()["detail"]


def test_session_expiration(client, db_session):
    expired_token = "test-expired-token"
    past_time = datetime.now(timezone.utc) - timedelta(hours=2)
    session = IntakeSession(
        session_token=expired_token,
        status="draft",
        expires_at=past_time,
    )
    db_session.add(session)
    db_session.commit()

    res = client.get(f"/api/intake/sessions/{expired_token}")
    assert res.status_code == 410
    assert "expired" in res.json()["detail"].lower()


def test_future_dob_rejected(client):
    create_res = client.post("/api/intake/sessions")
    token = create_res.json()["session_token"]

    future_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    payload = {
        "name": "Future Patient",
        "dob": future_date,
        "phone": "9876543210",
        "selected_complaints": ["Headache"],
        "duration": "1–2 days",
        "severity": 4,
    }
    res = client.post(f"/api/intake/sessions/{token}/submit", json=payload)
    assert res.status_code == 422
    assert "future" in res.text.lower()


def test_phone_validation_rules(client):
    create_res = client.post("/api/intake/sessions")
    token = create_res.json()["session_token"]

    base_payload = {
        "name": "Test Patient",
        "dob": "1992-05-10",
        "selected_complaints": ["Cough"],
        "duration": "1–2 days",
        "severity": 3,
    }

    # 1. Letters rejected
    res1 = client.post(
        f"/api/intake/sessions/{token}/submit",
        json={**base_payload, "phone": "98765abcde"},
    )
    assert res1.status_code == 422

    # 2. Symbols rejected
    res2 = client.post(
        f"/api/intake/sessions/{token}/submit",
        json={**base_payload, "phone": "98765@#$%^"},
    )
    assert res2.status_code == 422

    # 3. Fewer than 10 digits rejected
    res3 = client.post(
        f"/api/intake/sessions/{token}/submit",
        json={**base_payload, "phone": "987654321"},
    )
    assert res3.status_code == 422

    # 4. More than 10 digits rejected
    res4 = client.post(
        f"/api/intake/sessions/{token}/submit",
        json={**base_payload, "phone": "9876543210123"},
    )
    assert res4.status_code == 422

    # 5. Empty phone is valid (optional)
    res5 = client.post(
        f"/api/intake/sessions/{token}/submit",
        json={**base_payload, "phone": ""},
    )
    assert res5.status_code == 200


def test_structured_condition_details_intake(client):
    create_res = client.post("/api/intake/sessions")
    token = create_res.json()["session_token"]

    condition_details = {
        "Diabetes": {
            "type": "Type 1",
            "treatment": "Oral medication",
            "provenance": "patient-reported",
        },
        "Asthma": {
            "inhaler_frequency": "A few times a week",
            "recent_flare_up": "Yes, within the last month",
            "provenance": "patient-reported",
        },
        "High blood pressure": {
            "medication": "Yes",
            "last_reading": "Within the last week",
            "provenance": "patient-reported",
        },
    }

    payload = {
        "name": "Rohan Verma",
        "dob": "1994-06-15",
        "phone": "9876543210",
        "selected_complaints": ["Fever"],
        "duration": "3–5 days",
        "severity": 5,
        "conditions": ["Diabetes", "Asthma", "High blood pressure"],
        "adaptive_answers": {
            "Fever-0": "Gradually",
            "Diabetes-0": "Type 1",
            "Diabetes-1": "Oral medication",
            "Asthma-0": "A few times a week",
            "Asthma-1": "Yes, within the last month",
            "High blood pressure-0": "Yes",
            "High blood pressure-1": "Within the last week",
        },
        "condition_details": condition_details,
        "medications": "Metformin 500mg, Salbutamol inhaler",
        "allergies": "None reported",
        "additional_notes": "Patient feels tired and has mild fatigue.",
    }

    submit_res = client.post(f"/api/intake/sessions/{token}/submit", json=payload)
    assert submit_res.status_code == 200
    data = submit_res.json()

    # 1. Verify summary returned by submit retains structured condition_details
    assert "condition_details" in data["summary"]
    assert data["summary"]["condition_details"]["Diabetes"]["type"] == "Type 1"
    assert data["summary"]["condition_details"]["Diabetes"]["treatment"] == "Oral medication"
    assert data["summary"]["condition_details"]["Asthma"]["inhaler_frequency"] == "A few times a week"
    assert data["summary"]["condition_details"]["High blood pressure"]["last_reading"] == "Within the last week"

    # 2. Verify additional_notes is NOT polluted with condition details
    assert data["summary"]["additional_notes"] == "Patient feels tired and has mild fatigue."

    # 3. Verify Doctor Intake endpoint returns structured condition_details
    doc_res = client.get(f"/api/doctor/intake/{token}")
    assert doc_res.status_code == 200
    doc_summary = doc_res.json()["summary"]

    assert "condition_details" in doc_summary
    assert doc_summary["condition_details"]["Diabetes"]["type"] == "Type 1"
    assert doc_summary["condition_details"]["Diabetes"]["provenance"] == "patient-reported"
    assert doc_summary["condition_details"]["Asthma"]["inhaler_frequency"] == "A few times a week"
    assert doc_summary["condition_details"]["High blood pressure"]["last_reading"] == "Within the last week"

    # 4. Verify Doctor summary adaptive_responses only contains symptom questions
    assert "Fever Onset" in doc_summary["adaptive_responses"]
    assert "Diabetes-0" not in doc_summary["adaptive_responses"]
    assert "Asthma-0" not in doc_summary["adaptive_responses"]


def test_legacy_condition_notes_backward_compatibility(client):
    create_res = client.post("/api/intake/sessions")
    token = create_res.json()["session_token"]

    # Legacy submission: no condition_details in payload, condition answers flattened into additional_notes
    legacy_notes = (
        "Condition details: Diabetes (What type of diabetes do you have?): Type 1; "
        "Diabetes (Are you currently taking medication or insulin?): Oral medication\n"
        "Legacy free-form note."
    )
    payload = {
        "name": "Legacy Patient",
        "dob": "1988-02-14",
        "phone": "9876543210",
        "selected_complaints": ["Headache"],
        "duration": "1–2 days",
        "severity": 4,
        "conditions": ["Diabetes"],
        "adaptive_answers": {},
        "medications": "None",
        "allergies": "None",
        "additional_notes": legacy_notes,
    }

    submit_res = client.post(f"/api/intake/sessions/{token}/submit", json=payload)
    assert submit_res.status_code == 200

    # Query Doctor Intake endpoint to check backward-compatibility parsing
    doc_res = client.get(f"/api/doctor/intake/{token}")
    assert doc_res.status_code == 200
    doc_summary = doc_res.json()["summary"]

    # Verify legacy string was parsed into structured condition_details
    assert "condition_details" in doc_summary
    assert "Diabetes" in doc_summary["condition_details"]
    assert doc_summary["condition_details"]["Diabetes"]["type"] == "Type 1"
    assert doc_summary["condition_details"]["Diabetes"]["treatment"] == "Oral medication"
    assert doc_summary["condition_details"]["Diabetes"]["provenance"] == "patient-reported"

    # Verify additional_notes cleaned of legacy condition prefix
    assert doc_summary["additional_notes"] == "Legacy free-form note."


