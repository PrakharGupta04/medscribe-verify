import pytest
from fastapi.testclient import TestClient
from backend.app.core.config import settings


def test_health_reports_db_and_key(client: TestClient):
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert "db" in data
    assert "groq_key_configured" in data
    assert data["db"] == "ok"
    assert data["status"] in {"healthy", "degraded"}


def test_finalize_uses_supplied_doctor_name(client: TestClient):
    # 1. Create intake session
    s_res = client.post("/api/intake/sessions")
    assert s_res.status_code == 201
    token = s_res.json()["session_token"]

    # 2. Submit patient intake
    submit_payload = {
        "name": "Devin Consultation Test",
        "dob": "1994-04-12",
        "phone": "9876540199",
        "selected_complaints": ["Headache"],
        "duration": "2 days",
        "severity": 5,
        "additional_symptoms": ["fatigue"],
        "adaptive_answers": {"Headache-0": "Forehead"},
        "conditions": ["None of the above"],
        "medications": "None",
        "allergies": "Penicillin",
        "additional_notes": "Mild throbbing headache.",
    }
    sub_res = client.post(f"/api/intake/sessions/{token}/submit", json=submit_payload)
    assert sub_res.status_code == 200
    patient_id = sub_res.json()["patient_id"]

    # 3. Create consultation
    c_res = client.post(
        "/api/consultations",
        json={"patient_id": patient_id, "session_id": token},
    )
    assert c_res.status_code == 201
    consultation_id = c_res.json()["id"]

    # 4. Put transcript
    t_res = client.put(
        f"/api/consultations/{consultation_id}/transcript",
        json={"transcript": "Doctor: hello"},
    )
    assert t_res.status_code == 200

    # 5. Finalize with doctor_name
    f_res = client.post(
        f"/api/consultations/{consultation_id}/finalize",
        json={"doctor_name": "Dr. Test Person"},
    )
    assert f_res.status_code == 200
    final_record = f_res.json()["final_record"]
    assert final_record is not None
    assert final_record["doctor_name"] == "Dr. Test Person"


def test_finalize_falls_back_to_config_default(client: TestClient):
    # 1. Create intake session
    s_res = client.post("/api/intake/sessions")
    assert s_res.status_code == 201
    token = s_res.json()["session_token"]

    # 2. Submit patient intake
    submit_payload = {
        "name": "Fallback Doctor Test",
        "dob": "1990-01-01",
        "phone": "9876540188",
        "selected_complaints": ["Cough"],
        "duration": "3 days",
        "severity": 4,
        "conditions": ["None of the above"],
        "medications": "None",
        "allergies": "None",
    }
    sub_res = client.post(f"/api/intake/sessions/{token}/submit", json=submit_payload)
    assert sub_res.status_code == 200
    patient_id = sub_res.json()["patient_id"]

    # 3. Create consultation
    c_res = client.post(
        "/api/consultations",
        json={"patient_id": patient_id, "session_id": token},
    )
    assert c_res.status_code == 201
    consultation_id = c_res.json()["id"]

    # 4. Put transcript
    t_res = client.put(
        f"/api/consultations/{consultation_id}/transcript",
        json={"transcript": "Doctor: hello"},
    )
    assert t_res.status_code == 200

    # 5. Finalize with empty body {}
    f_res = client.post(
        f"/api/consultations/{consultation_id}/finalize",
        json={},
    )
    assert f_res.status_code == 200
    final_record = f_res.json()["final_record"]
    assert final_record is not None
    assert final_record["doctor_name"] == settings.DEFAULT_DOCTOR_NAME
