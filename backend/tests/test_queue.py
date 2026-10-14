def test_queue_flow_and_doctor_summary(client):
    # 1. Create and submit Patient A
    res_a = client.post("/api/intake/sessions")
    token_a = res_a.json()["session_token"]
    submit_a = client.post(
        f"/api/intake/sessions/{token_a}/submit",
        json={
            "name": "Patient Alpha",
            "selected_complaints": ["Headache"],
            "duration": "1–2 days",
            "severity": 4,
            "conditions": ["None of the above"],
            "medications": "Paracetamol",
            "allergies": "None",
            "additional_notes": "Mild pain",
        },
    )
    assert submit_a.status_code == 200
    data_a = submit_a.json()
    assert data_a["queue_position"] == 1

    # 2. Create and submit Patient B
    res_b = client.post("/api/intake/sessions")
    token_b = res_b.json()["session_token"]
    submit_b = client.post(
        f"/api/intake/sessions/{token_b}/submit",
        json={
            "name": "Patient Beta",
            "selected_complaints": ["Sore Throat"],
            "duration": "3–5 days",
            "severity": 8,
            "conditions": ["Asthma"],
            "medications": "Inhaler",
            "allergies": "Penicillin — rash",
            "additional_notes": "Difficulty swallowing",
        },
    )
    assert submit_b.status_code == 200
    data_b = submit_b.json()
    assert data_b["queue_position"] == 2

    # 3. Retrieve Queue
    q_res = client.get("/api/queue")
    assert q_res.status_code == 200
    q_data = q_res.json()
    assert q_data["total_waiting"] == 2
    assert q_data["items"][0]["patient_name"] == "Patient Alpha"
    assert q_data["items"][0]["position"] == 1
    assert q_data["items"][1]["patient_name"] == "Patient Beta"
    assert q_data["items"][1]["position"] == 2

    # 4. Doctor Pre-Consultation Summary for Patient Beta
    doc_res = client.get(f"/api/doctor/intake/{data_b['patient_id']}")
    assert doc_res.status_code == 200
    doc_data = doc_res.json()

    assert doc_data["patient"]["name"] == "Patient Beta"
    assert doc_data["summary"]["chief_complaint"] == "Sore Throat"
    assert doc_data["summary"]["severity"] == 8
    assert "Severe" in doc_data["summary"]["severity_label"]
    assert doc_data["summary"]["provenance"] == "patient-reported"
    assert len(doc_data["summary"]["allergy_flags"]) > 0
    assert "Penicillin" in doc_data["summary"]["allergy_flags"][0]
    assert "not been clinically verified" in doc_data["summary"]["clinical_notice"]


def test_isolated_demo_seeder(client):
    seed_res = client.post("/api/demo/seed")
    assert seed_res.status_code == 200
    data = seed_res.json()
    assert data["status"] in ("seeded", "exists")

    # Verify Sarah M. and James K. appear in queue
    q_res = client.get("/api/queue")
    assert q_res.status_code == 200
    q_data = q_res.json()
    assert q_data["total_waiting"] == 2
    assert any(p["patient_name"] == "Sarah M." for p in q_data["items"])


def test_remove_patient_from_queue(client):
    # 1. Create Patient 1
    res1 = client.post("/api/intake/sessions")
    token1 = res1.json()["session_token"]
    submit1 = client.post(
        f"/api/intake/sessions/{token1}/submit",
        json={
            "name": "Queue Patient 1",
            "selected_complaints": ["Fever"],
            "duration": "1–2 days",
            "severity": 5,
        },
    )
    assert submit1.status_code == 200
    entry1_id = submit1.json()["queue_entry_id"]
    patient1_id = submit1.json()["patient_id"]

    # 2. Create Patient 2
    res2 = client.post("/api/intake/sessions")
    token2 = res2.json()["session_token"]
    submit2 = client.post(
        f"/api/intake/sessions/{token2}/submit",
        json={
            "name": "Queue Patient 2",
            "selected_complaints": ["Cough"],
            "duration": "1–2 days",
            "severity": 3,
        },
    )
    assert submit2.status_code == 200
    entry2_id = submit2.json()["queue_entry_id"]

    # 3. Check queue before removal: Patient 1 is #1, Patient 2 is #2
    q_res = client.get("/api/queue")
    assert q_res.status_code == 200
    waiting_items = [i for i in q_res.json()["items"] if i["status"] == "waiting"]
    assert any(i["id"] == entry1_id and i["position"] == 1 for i in waiting_items)
    assert any(i["id"] == entry2_id and i["position"] == 2 for i in waiting_items)

    # 4. Safely remove Patient 1
    del_res = client.delete(f"/api/queue/{entry1_id}")
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "cancelled"

    # 5. Check queue after removal: Patient 1 is gone, Patient 2 moves up to position 1
    q_after = client.get("/api/queue")
    active_after = [i for i in q_after.json()["items"] if i["status"] == "waiting"]
    assert not any(i["id"] == entry1_id for i in active_after)
    p2_entry = next(i for i in active_after if i["id"] == entry2_id)
    assert p2_entry["position"] == 1

    # 6. Verify Patient 1 record, intake data, and patient details are COMPLETELY PRESERVED
    doc_res = client.get(f"/api/doctor/intake/{patient1_id}")
    assert doc_res.status_code == 200
    assert doc_res.json()["patient"]["name"] == "Queue Patient 1"
    assert doc_res.json()["summary"]["chief_complaint"] == "Fever"

