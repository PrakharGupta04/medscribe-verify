import pytest
from fastapi.testclient import TestClient


def test_consultation_creation_and_retrieval(client: TestClient):
    # 1. Create intake session in Module 1
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
    sub_data = sub_res.json()
    patient_id = sub_data["patient_id"]
    queue_id = sub_data["queue_entry_id"]

    # 3. Verify queue entry starts in "waiting" status
    q_res = client.get("/api/queue")
    assert q_res.status_code == 200
    queue_items = q_res.json()["items"]
    entry = next((i for i in queue_items if i["id"] == queue_id), None)
    assert entry is not None
    assert entry["status"] == "waiting"

    # 4. Start consultation via POST /api/consultations
    cons_res = client.post(
        "/api/consultations",
        json={"patient_id": patient_id, "session_id": token},
    )
    assert cons_res.status_code == 201
    cons_data = cons_res.json()

    assert cons_data["id"] is not None
    assert cons_data["patient_id"] == patient_id
    assert cons_data["status"] == "in-progress"  # Consultation.status is in-progress
    assert cons_data["transcript"] == ""
    assert "created_at" in cons_data
    consultation_id = cons_data["id"]

    # 5. Verify QueueEntry status transitioned to "in-consultation"
    # (consistent distinction: QueueEntry is "in-consultation", Consultation is "in-progress")
    q_res2 = client.get("/api/queue")
    assert q_res2.status_code == 200
    entry2 = next((i for i in q_res2.json()["items"] if i["id"] == queue_id), None)
    assert entry2 is not None
    assert entry2["status"] == "in-consultation"

    # 6. Verify idempotency: calling POST again returns existing active consultation
    cons_res2 = client.post(
        "/api/consultations",
        json={"patient_id": patient_id, "session_id": token},
    )
    assert cons_res2.status_code == 201
    assert cons_res2.json()["id"] == consultation_id

    # 7. Verify retrieval by ID via GET /api/consultations/{id}
    get_res = client.get(f"/api/consultations/{consultation_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == consultation_id
    assert get_res.json()["patient_id"] == patient_id
    assert get_res.json()["status"] == "in-progress"

    # 8. Verify retrieval by patient via GET /api/consultations/patient/{patient_id}
    p_cons_res = client.get(f"/api/consultations/patient/{patient_id}")
    assert p_cons_res.status_code == 200
    p_cons_list = p_cons_res.json()
    assert len(p_cons_list) >= 1
    assert any(c["id"] == consultation_id for c in p_cons_list)

    # 9. Verify 404 for non-existent consultation
    not_found_res = client.get("/api/consultations/non-existent-uuid-12345")
    assert not_found_res.status_code == 404

    # 10. Verify 404 for non-existent patient creation
    bad_patient_res = client.post(
        "/api/consultations",
        json={"patient_id": "non-existent-patient-999"},
    )
    assert bad_patient_res.status_code == 404

    # 11. Phase 2.2: Save manual transcript to consultation record
    sample_transcript = (
        "Doctor: How long have you had this fever?\n"
        "Patient: About three days with headache. Taking paracetamol twice daily."
    )
    t_res = client.put(
        f"/api/consultations/{consultation_id}/transcript",
        json={"transcript": sample_transcript},
    )
    assert t_res.status_code == 200
    assert t_res.json()["transcript"] == sample_transcript

    # 12. Verify persistence after retrieval (e.g. simulating page refresh)
    get_res2 = client.get(f"/api/consultations/{consultation_id}")
    assert get_res2.status_code == 200
    assert get_res2.json()["transcript"] == sample_transcript

    # 13. Verify accidental empty overwrite protection
    # Sending empty string without allow_clear=True must fail with 400
    empty_res = client.put(
        f"/api/consultations/{consultation_id}/transcript",
        json={"transcript": "   ", "allow_clear": False},
    )
    assert empty_res.status_code == 400

    # Confirm previous transcript was NOT cleared or lost
    get_res3 = client.get(f"/api/consultations/{consultation_id}")
    assert get_res3.status_code == 200
    assert get_res3.json()["transcript"] == sample_transcript

    # 14. Explicit clear with allow_clear=True succeeds
    clear_res = client.put(
        f"/api/consultations/{consultation_id}/transcript",
        json={"transcript": "", "allow_clear": True},
    )
    assert clear_res.status_code == 200
    assert clear_res.json()["transcript"] == ""

    # 15. Verify 404 when updating non-existent consultation
    bad_update_res = client.put(
        "/api/consultations/non-existent-consultation/transcript",
        json={"transcript": "Test text"},
    )
    assert bad_update_res.status_code == 404


def test_consultation_voice_transcription_integration(client: TestClient):
    import base64, wave, io

    # 1. Create intake session and patient
    s_res = client.post("/api/intake/sessions")
    token = s_res.json()["session_token"]
    sub_res = client.post(
        f"/api/intake/sessions/{token}/submit",
        json={
            "name": "Voice Patient Test",
            "selected_complaints": ["Cough"],
            "duration": "1 week",
            "severity": 4,
            "conditions": ["None of the above"],
        },
    )
    patient_id = sub_res.json()["patient_id"]

    # 2. Start consultation
    cons_res = client.post(
        "/api/consultations",
        json={"patient_id": patient_id, "session_id": token},
    )
    consultation_id = cons_res.json()["id"]

    # 3. Voice audio transcription (reusing working /api/intake/transcribe)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00" * 32000)
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    voice_res = client.post(
        "/api/intake/transcribe",
        json={"audio_base64": b64, "filename": "audio.wav", "language": "en"},
    )
    assert voice_res.status_code == 200
    transcribed_text = voice_res.json().get("text", "")

    # 4. Save transcribed voice text (or edited transcript) to the consultation record
    consultation_transcript = (
        transcribed_text
        if transcribed_text
        else "Doctor: Did you experience any cough? Patient: Yes, dry cough."
    )
    save_res = client.put(
        f"/api/consultations/{consultation_id}/transcript",
        json={"transcript": consultation_transcript},
    )
    assert save_res.status_code == 200
    assert save_res.json()["transcript"] == consultation_transcript

    # 5. Verify database persistence
    get_res = client.get(f"/api/consultations/{consultation_id}")
    assert get_res.status_code == 200
    assert get_res.json()["transcript"] == consultation_transcript


def test_consultation_clinical_extraction(client: TestClient):
    # 1. Create intake session and patient
    s_res = client.post("/api/intake/sessions")
    token = s_res.json()["session_token"]
    sub_res = client.post(
        f"/api/intake/sessions/{token}/submit",
        json={
            "name": "Extraction Test Patient",
            "selected_complaints": ["Fever"],
            "duration": "3 days",
            "severity": 6,
            "conditions": ["None of the above"],
        },
    )
    patient_id = sub_res.json()["patient_id"]

    # 2. Start consultation
    cons_res = client.post(
        "/api/consultations",
        json={"patient_id": patient_id, "session_id": token},
    )
    consultation_id = cons_res.json()["id"]

    # 3. Test empty transcript error (must not call LLM)
    empty_extract = client.post(f"/api/consultations/{consultation_id}/extract")
    assert empty_extract.status_code == 400
    assert "empty" in empty_extract.json()["detail"].lower()

    # 4. Save deterministic consultation transcript
    deterministic_transcript = (
        "Patient reports fever for three days with headache. "
        "Patient is currently taking paracetamol twice daily. "
        "Patient reports an allergy to penicillin that causes a rash. "
        "Patient denies vomiting."
    )
    save_t = client.put(
        f"/api/consultations/{consultation_id}/transcript",
        json={"transcript": deterministic_transcript},
    )
    assert save_t.status_code == 200

    # 5. Run clinical information extraction
    extract_res = client.post(f"/api/consultations/{consultation_id}/extract")
    assert extract_res.status_code == 200
    ext_data = extract_res.json()

    # Verify raw transcript is completely preserved and untouched
    assert ext_data["transcript"] == deterministic_transcript
    assert ext_data["extracted_clinical_data"] is not None

    clinical = ext_data["extracted_clinical_data"]
    assert clinical["provenance"] == "ai-extracted"

    # Verify symptoms extracted correctly
    symptom_names = [s["name"].lower() for s in clinical["symptoms"]]
    assert any("fever" in name for name in symptom_names)
    assert any("headache" in name for name in symptom_names)

    # Check duration for fever if extracted
    fever_symptom = next((s for s in clinical["symptoms"] if "fever" in s["name"].lower()), None)
    if fever_symptom and fever_symptom["duration"]:
        assert any(d in fever_symptom["duration"].lower() for d in ["three", "3", "days"])

    # Verify medications
    med_names = [m["name"].lower() for m in clinical["medications"]]
    assert any("paracetamol" in name for name in med_names)
    paracetamol = next((m for m in clinical["medications"] if "paracetamol" in m["name"].lower()), None)
    if paracetamol and paracetamol["frequency"]:
        assert any(f in paracetamol["frequency"].lower() for f in ["twice", "2x", "daily", "day"])

    # Verify allergies
    allergy_substances = [a["substance"].lower() for a in clinical["allergies"]]
    assert any("penicillin" in sub for sub in allergy_substances)
    penicillin = next((a for a in clinical["allergies"] if "penicillin" in a["substance"].lower()), None)
    if penicillin and penicillin["reaction"]:
        assert "rash" in penicillin["reaction"].lower()

    # Verify negative findings
    neg_findings = " ".join(clinical["negative_findings"]).lower()
    assert "vomit" in neg_findings

    # Verify no unmentioned facts were hallucinated
    # Vital signs (blood pressure, heart rate, oxygen) must NOT be in observations if unmentioned
    obs_text = " ".join(clinical["observations"]).lower()
    assert "blood pressure" not in obs_text
    assert "heart rate" not in obs_text
    assert "oxygen" not in obs_text

    # 6. Verify persistence upon retrieval (simulating page reload)
    get_res = client.get(f"/api/consultations/{consultation_id}")
    assert get_res.status_code == 200
    retrieved_data = get_res.json()
    assert retrieved_data["transcript"] == deterministic_transcript
    assert retrieved_data["extracted_clinical_data"] is not None
    assert len(retrieved_data["extracted_clinical_data"]["symptoms"]) >= 2


def test_consultation_extraction_error_preserves_transcript_and_data(client: TestClient, monkeypatch):
    # 1. Create session, patient, and consultation
    s_res = client.post("/api/intake/sessions")
    token = s_res.json()["session_token"]
    sub_res = client.post(
        f"/api/intake/sessions/{token}/submit",
        json={
            "name": "Error Recovery Patient",
            "selected_complaints": ["Headache"],
            "duration": "1 day",
            "severity": 3,
            "conditions": ["None of the above"],
        },
    )
    patient_id = sub_res.json()["patient_id"]
    cons_res = client.post("/api/consultations", json={"patient_id": patient_id, "session_id": token})
    consultation_id = cons_res.json()["id"]

    # 2. Save transcript
    raw_transcript = "Patient reports mild headache. Takes aspirin."
    client.put(f"/api/consultations/{consultation_id}/transcript", json={"transcript": raw_transcript})

    # 3. Simulate Groq failure
    from backend.app.services import extraction_service

    def mock_failure(transcript):
        raise RuntimeError("Simulated Groq timeout error")

    monkeypatch.setattr(extraction_service, "extract_clinical_facts_groq", mock_failure)

    # 4. Trigger extraction
    err_res = client.post(f"/api/consultations/{consultation_id}/extract")
    assert err_res.status_code == 502
    assert "Simulated Groq timeout error" in err_res.json()["detail"]

    # 5. Verify raw transcript remains untouched in the database
    get_res = client.get(f"/api/consultations/{consultation_id}")
    assert get_res.status_code == 200
    assert get_res.json()["transcript"] == raw_transcript


def test_consultation_hindi_clinical_extraction_fidelity(client: TestClient):
    # 1. Create intake session and patient
    s_res = client.post("/api/intake/sessions")
    token = s_res.json()["session_token"]
    sub_res = client.post(
        f"/api/intake/sessions/{token}/submit",
        json={
            "name": "Hindi Fidelity Patient",
            "selected_complaints": ["Fever"],
            "duration": "3 days",
            "severity": 6,
            "conditions": ["None of the above"],
        },
    )
    patient_id = sub_res.json()["patient_id"]

    # 2. Start consultation
    cons_res = client.post(
        "/api/consultations",
        json={"patient_id": patient_id, "session_id": token},
    )
    consultation_id = cons_res.json()["id"]

    # 3. Save Hindi consultation transcript
    hindi_transcript = (
        "मुझे तीन दिन से तेज बुखार और सिर दर्द है। "
        "मैं पैरासिटामोल दिन में दो बार ले रहा हूँ। "
        "मुझे पेनिसिलिन से एलर्जी है और चकत्ते हो जाते हैं। "
        "उल्टी नहीं है।"
    )
    save_res = client.put(
        f"/api/consultations/{consultation_id}/transcript",
        json={"transcript": hindi_transcript},
    )
    assert save_res.status_code == 200

    # 4. Extract clinical information
    extract_res = client.post(f"/api/consultations/{consultation_id}/extract")
    assert extract_res.status_code == 200
    ext_data = extract_res.json()

    # Verify transcript is preserved exactly as Hindi in the consultation record
    assert ext_data["transcript"] == hindi_transcript
    clinical = ext_data["extracted_clinical_data"]
    assert clinical is not None
    assert clinical["provenance"] == "ai-extracted"

    # Verify symptoms: Fever and Headache
    symptom_names = [s["name"].lower() for s in clinical["symptoms"]]
    assert any("fever" in name for name in symptom_names)
    assert any("headache" in name for name in symptom_names)

    # Check duration (3 days) if extracted
    fever_symptom = next((s for s in clinical["symptoms"] if "fever" in s["name"].lower()), None)
    if fever_symptom and fever_symptom["duration"]:
        assert any(d in fever_symptom["duration"].lower() for d in ["3", "three", "day", "दिन"])
    # Check conversational intensity fidelity: "तेज बुखार" should not be forced into severity="severe"
    if fever_symptom and fever_symptom["severity"]:
        assert fever_symptom["severity"].lower() != "severe"

    # Verify medications: Paracetamol twice daily
    med_names = [m["name"].lower() for m in clinical["medications"]]
    assert any("paracetamol" in name for name in med_names)
    paracetamol = next((m for m in clinical["medications"] if "paracetamol" in m["name"].lower()), None)
    assert paracetamol is not None
    if paracetamol.get("frequency"):
        freq = paracetamol["frequency"].lower()
        assert any(term in freq for term in ["twice", "2", "two", "दिन में दो बार", "daily"])

    # Verify allergy: Penicillin allergy with reaction "rash" rather than "hives"
    allergy_substances = [a["substance"].lower() for a in clinical["allergies"]]
    assert any("penicillin" in sub for sub in allergy_substances)
    penicillin = next((a for a in clinical["allergies"] if "penicillin" in a["substance"].lower()), None)
    assert penicillin is not None
    assert penicillin.get("reaction") is not None
    reaction_lower = penicillin["reaction"].lower()
    assert "rash" in reaction_lower
    assert "hive" not in reaction_lower
    assert "urticaria" not in reaction_lower

    # Verify negative finding: Vomiting
    neg_findings = " ".join(clinical["negative_findings"]).lower()
    assert "vomit" in neg_findings


def test_soap_draft_empty_transcript_and_missing_extraction_protection(client: TestClient):
    # 1. Create intake session, patient, and consultation
    s_res = client.post("/api/intake/sessions")
    token = s_res.json()["session_token"]
    sub_res = client.post(
        f"/api/intake/sessions/{token}/submit",
        json={
            "name": "SOAP Precondition Patient",
            "selected_complaints": ["Headache"],
            "duration": "1 day",
            "severity": 4,
            "conditions": ["None of the above"],
        },
    )
    patient_id = sub_res.json()["patient_id"]
    cons_res = client.post("/api/consultations", json={"patient_id": patient_id, "session_id": token})
    consultation_id = cons_res.json()["id"]

    # 2. Empty transcript rejection (HTTP 400)
    empty_res = client.post(f"/api/consultations/{consultation_id}/soap-draft")
    assert empty_res.status_code == 400
    assert "transcript is empty" in empty_res.json()["detail"].lower()

    # 3. Add transcript but DO NOT extract clinical information yet
    client.put(
        f"/api/consultations/{consultation_id}/transcript",
        json={"transcript": "Patient reports mild headache for one day. No fever."},
    )

    # 4. Attempt SOAP generation without prior clinical extraction -> must return 400
    no_ext_res = client.post(f"/api/consultations/{consultation_id}/soap-draft")
    assert no_ext_res.status_code == 400
    assert "clinical information must be extracted before" in no_ext_res.json()["detail"].lower()

    # 5. Verify existing transcript was preserved untouched
    get_res = client.get(f"/api/consultations/{consultation_id}")
    assert get_res.status_code == 200
    assert "mild headache" in get_res.json()["transcript"]
    assert get_res.json()["soap_draft"] is None


def test_soap_generation_english_and_absence_fidelity(client: TestClient):
    # 1. Create patient and consultation
    s_res = client.post("/api/intake/sessions")
    token = s_res.json()["session_token"]
    sub_res = client.post(
        f"/api/intake/sessions/{token}/submit",
        json={
            "name": "English SOAP Fidelity Patient",
            "selected_complaints": ["Fever"],
            "duration": "3 days",
            "severity": 5,
            "conditions": ["None of the above"],
        },
    )
    patient_id = sub_res.json()["patient_id"]
    cons_res = client.post("/api/consultations", json={"patient_id": patient_id, "session_id": token})
    consultation_id = cons_res.json()["id"]

    # 2. Consultation transcript with NO objective vitals, NO clinician diagnosis, and NO clinician plan
    transcript = (
        "Patient: I have had a fever and headache for three days. "
        "I am taking paracetamol twice daily. "
        "I am allergic to penicillin and get a rash. "
        "I deny any vomiting. I wonder if I might have dengue."
    )
    client.put(f"/api/consultations/{consultation_id}/transcript", json={"transcript": transcript})

    # 3. Run Phase 2.3 clinical extraction first
    ext_res = client.post(f"/api/consultations/{consultation_id}/extract")
    assert ext_res.status_code == 200
    assert ext_res.json()["extracted_clinical_data"] is not None

    # 4. Generate SOAP draft
    soap_res = client.post(f"/api/consultations/{consultation_id}/soap-draft")
    assert soap_res.status_code == 200
    cons_data = soap_res.json()
    soap = cons_data["soap_draft"]
    assert soap is not None

    # Verify S (Subjective) contains patient complaints, allergy, and negative findings
    s_text = soap["subjective"].lower()
    assert "fever" in s_text
    assert "headache" in s_text
    assert "paracetamol" in s_text
    assert "penicillin" in s_text
    assert "rash" in s_text
    assert "vomit" in s_text

    # Verify patient speculation ("dengue") is NOT in Assessment
    assert "dengue" not in soap["assessment"].lower()

    # Verify Absence Fidelity: O, A, P match exact sentinel values when absent
    assert soap["objective"] == "Not documented."
    assert soap["assessment"] == "Not explicitly documented."
    assert soap["plan"] == "Not documented."
    assert soap["provenance"] == "ai-generated-draft-unverified"


def test_soap_generation_hindi_normalization(client: TestClient):
    # 1. Create patient and consultation
    s_res = client.post("/api/intake/sessions")
    token = s_res.json()["session_token"]
    sub_res = client.post(
        f"/api/intake/sessions/{token}/submit",
        json={
            "name": "Hindi SOAP Patient",
            "selected_complaints": ["Fever"],
            "duration": "3 days",
            "severity": 6,
            "conditions": ["None of the above"],
        },
    )
    patient_id = sub_res.json()["patient_id"]
    cons_res = client.post("/api/consultations", json={"patient_id": patient_id, "session_id": token})
    consultation_id = cons_res.json()["id"]

    # 2. Hindi consultation transcript with "चकत्ते"
    hindi_transcript = (
        "मुझे तीन दिन से तेज बुखार और सिर दर्द है। "
        "मैं पैरासिटामोल दिन में दो बार ले रहा हूँ। "
        "मुझे पेनिसिलिन से एलर्जी है और चकत्ते हो जाते हैं। "
        "उल्टी नहीं है।"
    )
    client.put(f"/api/consultations/{consultation_id}/transcript", json={"transcript": hindi_transcript})

    # 3. Phase 2.3 extraction
    ext_res = client.post(f"/api/consultations/{consultation_id}/extract")
    assert ext_res.status_code == 200

    # 4. Generate SOAP draft
    soap_res = client.post(f"/api/consultations/{consultation_id}/soap-draft")
    assert soap_res.status_code == 200
    soap = soap_res.json()["soap_draft"]

    # Verify Subjective is normalized to English clinical terminology
    s_text = soap["subjective"].lower()
    assert "fever" in s_text
    assert "headache" in s_text
    assert "paracetamol" in s_text
    assert "penicillin" in s_text
    # Fidelity rule: rash instead of hives/urticaria
    assert "rash" in s_text
    assert "hive" not in s_text
    assert "urticaria" not in s_text
    assert "vomit" in s_text

    # Since no objective vitals, doctor diagnosis, or plan were in Hindi transcript:
    assert soap["objective"] == "Not documented."
    assert soap["assessment"] == "Not explicitly documented."
    assert soap["plan"] == "Not documented."


def test_soap_presence_fidelity_explicit_diagnosis_and_plan(client: TestClient):
    # 1. Create patient and consultation
    s_res = client.post("/api/intake/sessions")
    token = s_res.json()["session_token"]
    sub_res = client.post(
        f"/api/intake/sessions/{token}/submit",
        json={
            "name": "Explicit Diagnosis Patient",
            "selected_complaints": ["Sore throat"],
            "duration": "2 days",
            "severity": 5,
            "conditions": ["None of the above"],
        },
    )
    patient_id = sub_res.json()["patient_id"]
    cons_res = client.post("/api/consultations", json={"patient_id": patient_id, "session_id": token})
    consultation_id = cons_res.json()["id"]

    # 2. Consultation with EXPLICIT exam findings, clinician diagnosis, and clinician plan
    transcript = (
        "Patient: I have a sore throat for 2 days. I think I have COVID.\n"
        "Doctor: On examination, tonsils are erythematous with exudate. Temperature is 101F.\n"
        "Doctor: My clinical diagnosis is Acute Streptococcal Pharyngitis.\n"
        "Doctor: The plan is Amoxicillin 500mg three times daily for 10 days and throat lozenges PRN."
    )
    client.put(f"/api/consultations/{consultation_id}/transcript", json={"transcript": transcript})

    # 3. Phase 2.3 extraction
    ext_res = client.post(f"/api/consultations/{consultation_id}/extract")
    assert ext_res.status_code == 200

    # 4. Generate SOAP draft
    soap_res = client.post(f"/api/consultations/{consultation_id}/soap-draft")
    assert soap_res.status_code == 200
    soap = soap_res.json()["soap_draft"]

    # Subjective has patient's sore throat
    assert "sore throat" in soap["subjective"].lower()

    # Objective captures explicitly documented examination / temp
    assert soap["objective"] != "Not documented."
    assert any(term in soap["objective"].lower() for term in ["tonsil", "exudate", "101", "erythematous", "exam"])

    # Assessment preserves explicit doctor diagnosis
    assert soap["assessment"] != "Not explicitly documented."
    assert "pharyngitis" in soap["assessment"].lower()
    # Patient self-suspicion ("COVID") must NOT be in Assessment
    assert "covid" not in soap["assessment"].lower()

    # Plan preserves explicit doctor prescription / plan
    assert soap["plan"] != "Not documented."
    assert "amoxicillin" in soap["plan"].lower()


def test_soap_generation_failure_preserves_existing_data(client: TestClient, monkeypatch):
    # 1. Create patient, consultation, transcript, and extraction
    s_res = client.post("/api/intake/sessions")
    token = s_res.json()["session_token"]
    sub_res = client.post(
        f"/api/intake/sessions/{token}/submit",
        json={
            "name": "Failure Resilience Patient",
            "selected_complaints": ["Cough"],
            "duration": "4 days",
            "severity": 3,
            "conditions": ["None of the above"],
        },
    )
    patient_id = sub_res.json()["patient_id"]
    cons_res = client.post("/api/consultations", json={"patient_id": patient_id, "session_id": token})
    consultation_id = cons_res.json()["id"]

    transcript = "Patient has mild dry cough for four days. Denies shortness of breath."
    client.put(f"/api/consultations/{consultation_id}/transcript", json={"transcript": transcript})
    ext_res = client.post(f"/api/consultations/{consultation_id}/extract")
    assert ext_res.status_code == 200

    # 2. Simulate Groq failure during SOAP generation
    from backend.app.services import soap_service

    def mock_failure(transcript, clinical_data):
        raise RuntimeError("Simulated Groq 500 internal error during SOAP synthesis")

    monkeypatch.setattr(soap_service, "generate_soap_draft_groq", mock_failure)

    # 3. Attempt SOAP generation -> fails with 502
    err_res = client.post(f"/api/consultations/{consultation_id}/soap-draft")
    assert err_res.status_code == 502
    assert "Simulated Groq 500" in err_res.json()["detail"]

    # 4. Verify existing transcript and extraction are preserved intact
    get_res = client.get(f"/api/consultations/{consultation_id}")
    assert get_res.status_code == 200
    assert get_res.json()["transcript"] == transcript
    assert get_res.json()["extracted_clinical_data"] is not None
    assert get_res.json()["soap_draft"] is None


def test_soap_draft_persistence_and_update(client: TestClient):
    # 1. Create patient and consultation
    s_res = client.post("/api/intake/sessions")
    token = s_res.json()["session_token"]
    sub_res = client.post(
        f"/api/intake/sessions/{token}/submit",
        json={
            "name": "Persistence Patient",
            "selected_complaints": ["Headache"],
            "duration": "1 day",
            "severity": 3,
            "conditions": ["None of the above"],
        },
    )
    patient_id = sub_res.json()["patient_id"]
    cons_res = client.post("/api/consultations", json={"patient_id": patient_id, "session_id": token})
    consultation_id = cons_res.json()["id"]

    client.put(
        f"/api/consultations/{consultation_id}/transcript",
        json={"transcript": "Patient has mild headache. Takes paracetamol."},
    )
    ext_res = client.post(f"/api/consultations/{consultation_id}/extract")
    assert ext_res.status_code == 200
    gen_res = client.post(f"/api/consultations/{consultation_id}/soap-draft")
    assert gen_res.status_code == 200

    # 2. Edit the draft using PUT /api/consultations/{consultation_id}/soap-draft
    update_payload = {
        "subjective": "Patient reports tension headache for 1 day, improved with rest.",
        "objective": "BP 120/80 mmHg, alert and oriented x3.",
        "assessment": "Tension-type headache.",
        "plan": "Continue hydration and paracetamol PRN.",
    }
    put_res = client.put(f"/api/consultations/{consultation_id}/soap-draft", json=update_payload)
    assert put_res.status_code == 200
    updated_soap = put_res.json()["soap_draft"]
    assert updated_soap["subjective"] == update_payload["subjective"]
    assert updated_soap["objective"] == update_payload["objective"]
    assert updated_soap["assessment"] == update_payload["assessment"]
    assert updated_soap["plan"] == update_payload["plan"]

    # 3. Verify persistence across GET /api/consultations/{consultation_id} (simulating page reload)
    get_res = client.get(f"/api/consultations/{consultation_id}")
    assert get_res.status_code == 200
    persisted_soap = get_res.json()["soap_draft"]
    assert persisted_soap["subjective"] == update_payload["subjective"]
    assert persisted_soap["assessment"] == update_payload["assessment"]


