import base64
import json
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.normalization_service import (
    normalize_to_clinical_english,
    is_hindi_or_hinglish,
)


def test_is_hindi_or_hinglish():
    # Pure English
    assert not is_hindi_or_hinglish("Penicillin allergy causing rash")
    assert not is_hindi_or_hinglish("Take paracetamol 500mg once daily")

    # Devanagari Hindi
    assert is_hindi_or_hinglish("मुझे दो दिन से बुखार है")
    assert is_hindi_or_hinglish("पेनिसिलिन से एलर्जी")

    # Hinglish
    assert is_hindi_or_hinglish("Mujhe 3 din se bukhar aur gale me dard hai")
    assert is_hindi_or_hinglish("Sulfa dawai se allergic reaction hota hai")


def test_normalize_to_clinical_english():
    # English stays English
    en_input = "Penicillin allergy with mild skin rash"
    assert normalize_to_clinical_english(en_input) == en_input

    # Hindi Devanagari translates to English
    hi_input = "मुझे तीन दिन से तेज बुखार है"
    hi_norm = normalize_to_clinical_english(hi_input)
    assert hi_norm != hi_input
    assert any(w in hi_norm.lower() for w in ["fever", "three", "days"])

    # Hinglish translates to English
    hing_input = "Mujhe paracetamol lene ke baad bhi bukhar kam nahi hua"
    hing_norm = normalize_to_clinical_english(hing_input)
    assert hing_norm != hing_input
    assert any(w in hing_norm.lower() for w in ["fever", "paracetamol", "subside", "reduce", "temperature"])


def test_english_text_to_english_doctor_summary(client: TestClient):
    # 1. Create session
    s_res = client.post("/api/intake/sessions")
    token = s_res.json()["session_token"]

    # 2. Submit English intake
    payload = {
        "name": "Sarah English",
        "dob": "1995-03-12",
        "phone": "9876540101",
        "selected_complaints": ["Headache"],
        "duration": "3–5 days",
        "severity": 6,
        "additional_symptoms": ["nausea"],
        "adaptive_answers": {"Headache-0": "Forehead"},
        "conditions": ["None of the above"],
        "medications": "Ibuprofen 400mg as needed",
        "allergies": "Penicillin — rash",
        "additional_notes": "Headache worsens under bright fluorescent light.",
    }
    sub_res = client.post(f"/api/intake/sessions/{token}/submit", json=payload)
    assert sub_res.status_code == 200
    queue_id = sub_res.json()["queue_entry_id"]

    # 3. Doctor views summary
    doc_res = client.get(f"/api/doctor/intake/{queue_id}")
    assert doc_res.status_code == 200
    doc_data = doc_res.json()
    summary = doc_data["summary"]

    assert summary["chief_complaint"] == "Headache"
    assert "Ibuprofen" in summary["medications"]
    assert "Penicillin" in summary["allergies"]
    assert any("Penicillin" in flag for flag in summary["allergy_flags"])
    assert "bright fluorescent light" in summary["additional_notes"]


def test_hindi_text_to_english_doctor_summary(client: TestClient):
    # 1. Create session
    s_res = client.post("/api/intake/sessions")
    token = s_res.json()["session_token"]

    # 2. Submit Hindi Devanagari intake
    payload = {
        "name": "Aarav Sharma",
        "dob": "1990-08-15",
        "phone": "9876540102",
        "selected_complaints": ["Fever"],
        "duration": "3–5 days",
        "severity": 8,
        "additional_symptoms": ["chills"],
        "adaptive_answers": {"Fever-0": "Suddenly"},
        "conditions": ["None of the above"],
        "medications": "पैरासिटामोल दिन में दो बार",
        "allergies": "पेनिसिलिन से गंभीर एलर्जी और चकत्ते",
        "additional_notes": "मुझे तीन दिन से तेज बुखार और ठंड लग रही है।",
    }
    sub_res = client.post(f"/api/intake/sessions/{token}/submit", json=payload)
    assert sub_res.status_code == 200
    queue_id = sub_res.json()["queue_entry_id"]

    # 3. Doctor views summary
    doc_res = client.get(f"/api/doctor/intake/{queue_id}")
    assert doc_res.status_code == 200
    doc_data = doc_res.json()
    summary = doc_data["summary"]

    # Doctor report must be in English
    assert summary["chief_complaint"] == "Fever"
    # Medications should be normalized to English
    assert any(w in summary["medications"].lower() for w in ["paracetamol", "twice", "daily", "day"])
    # Allergies should be normalized to English and trigger allergy flags
    assert "penicillin" in summary["allergies"].lower()
    assert any("Penicillin" in flag for flag in summary["allergy_flags"])
    # Additional notes should be normalized to English
    assert any(w in summary["additional_notes"].lower() for w in ["fever", "chills", "three", "days"])

    # Check that raw input is preserved in draft_data
    session_res = client.get(f"/api/intake/sessions/{token}")
    draft = session_res.json().get("draft_data")
    assert "पैरासिटामोल" in draft["medications"]


def test_hinglish_text_to_english_doctor_summary(client: TestClient):
    # 1. Create session
    s_res = client.post("/api/intake/sessions")
    token = s_res.json()["session_token"]

    # 2. Submit Hinglish intake
    payload = {
        "name": "Priya Patel",
        "dob": "1992-01-20",
        "phone": "9876540103",
        "selected_complaints": ["Stomach Pain"],
        "duration": "1–2 days",
        "severity": 7,
        "additional_symptoms": ["nausea"],
        "adaptive_answers": {"Stomach Pain-0": "Upper abdomen"},
        "conditions": ["None of the above"],
        "medications": "Antacid syrup khana khane ke baad",
        "allergies": "Sulfa dawai se allergic reaction hota hai",
        "additional_notes": "Pet me bohot tej jalan aur ulti jaisa lag raha hai",
    }
    sub_res = client.post(f"/api/intake/sessions/{token}/submit", json=payload)
    assert sub_res.status_code == 200
    queue_id = sub_res.json()["queue_entry_id"]

    # 3. Doctor views summary
    doc_res = client.get(f"/api/doctor/intake/{queue_id}")
    assert doc_res.status_code == 200
    doc_data = doc_res.json()
    summary = doc_data["summary"]

    # Doctor summary must be in English
    assert summary["chief_complaint"] == "Stomach Pain"
    assert any(w in summary["medications"].lower() for w in ["antacid", "syrup", "meal", "food", "after"])
    assert "sulfa" in summary["allergies"].lower()
    assert any("Sulfa" in flag for flag in summary["allergy_flags"])
    assert any(w in summary["additional_notes"].lower() for w in ["stomach", "burning", "nausea", "vomit", "abdomen"])

    # Check raw input preservation in draft_data
    session_res = client.get(f"/api/intake/sessions/{token}")
    draft = session_res.json().get("draft_data")
    assert "Sulfa dawai" in draft["allergies"]


def test_voice_transcription_endpoint(client: TestClient):
    # Create minimal silent or speech wav in base64
    import wave, io
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b'\x00' * 32000)
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    res = client.post(
        "/api/intake/transcribe",
        json={"audio_base64": b64, "filename": "audio.wav", "language": "en"},
    )
    assert res.status_code == 200
    assert "text" in res.json()
