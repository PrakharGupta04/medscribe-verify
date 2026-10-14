import json
import re
import time
from datetime import datetime, timezone
from typing import Optional
import httpx

from backend.app.core.config import settings
from backend.app.schemas.consultation import (
    ClinicalExtraction,
    ExtractedSymptom,
    ExtractedMedication,
    ExtractedAllergy,
)

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
EXTRACTION_MODEL = "qwen/qwen3.8-27b"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


EXTRACTION_SYSTEM_PROMPT = """You are an expert, strict clinical information extraction engine.
Your sole job is to extract factual clinical statements EXPLICITLY present in the provided doctor-patient consultation transcript into structured JSON.

CRITICAL CLINICAL SAFETY & LANGUAGE RULES:
1. OUTPUT LANGUAGE: Regardless of whether the consultation transcript contains English, Hindi (Devanagari), or Hinglish (Roman Hindi), ALL extracted clinical concepts, symptom names, medication instructions, allergy reactions, observations, diagnoses, plan items, and negative findings in the JSON output MUST be in standard, clear English clinical terminology (e.g., 'Fever' for 'बुखार'/'bukhar', 'Headache' for 'सिर दर्द'/'sar dard', 'Vomiting' for 'उल्टी'/'ulti').
2. SOURCE FIDELITY OVER CLINICAL SPECIFICITY:
   - Extracted facts must NEVER become more clinically specific than what the raw transcript explicitly supports.
   - Specifically, the Hindi term "चकत्ते" (or romanized "chakatte") must be translated/extracted strictly as "rash" or "rashes", NEVER as "hives" or "urticaria", unless the transcript explicitly stated the clinical terms hives or urticaria.
   - Do NOT convert conversational or colloquial intensity into a formal clinical severity value unless the wording clearly supports that specific severity. For example, "तेज बुखार" ("high fever") may be preserved as Fever with details="high fever" (or details="तेज बुखार"), rather than automatically assigning severity="severe".
3. NEVER hallucinate, infer, speculate, extrapolate, or invent any clinical fact.
4. If vital signs (blood pressure, temperature, heart rate, oxygen saturation), laboratory values, or exam findings are NOT explicitly stated in the transcript, DO NOT INVENT THEM. Leave the 'observations' list empty or omit them.
5. If a diagnosis is NOT explicitly stated by the doctor or patient in the transcript, DO NOT INVENT A DIAGNOSIS. Leave 'diagnoses' empty.
6. If a plan, prescription, or treatment is NOT explicitly stated, DO NOT INVENT A PLAN. Leave 'plan' empty.
7. Accurately distinguish positive findings from negative findings:
   - Statements like "patient denies vomiting", "no chest pain", "no ear pain", "fever subsided", "उल्टी नहीं है" MUST be placed into 'negative_findings'.
   - Do NOT turn negative findings into positive symptoms.
8. For symptoms:
   - 'name': The symptom name in English (e.g. "Fever", "Headache", "Sore throat").
   - 'duration': ONLY if explicitly mentioned (e.g. "3 days", "तीन दिन"), else null.
   - 'severity': ONLY if a formal severity rating is explicitly stated (e.g. "6/10", "mild", "severe"). Do NOT convert conversational descriptors like "तेज" / "high" into severity="severe"; put conversational qualifiers in 'details' instead.
   - 'onset': ONLY if explicitly mentioned (e.g. "gradual", "sudden"), else null.
   - 'details': Any explicit qualifiers (e.g. "high fever", "throbbing"), else null.
9. For medications:
   - 'name': The medication name in English (e.g. "Paracetamol", "Amoxicillin").
   - 'dose': ONLY if explicitly stated (e.g. "500mg"), else null.
   - 'frequency': ONLY if explicitly stated in English (e.g. "twice daily", "PRN"), else null.
   - 'status': Explicit status if stated (e.g. "active", "discontinued", "stopped yesterday", "PRN"), else null.
10. For allergies:
   - 'substance': The drug or food substance in English (e.g. "Penicillin").
   - 'reaction': Explicit reaction in English (e.g. "rash" for "चकत्ते", NOT "hives" or "urticaria" unless explicitly stated).
   - 'severity': Explicit severity, else null.
11. Return ONLY a valid, parseable JSON object matching this schema:
{
  "symptoms": [
    {"name": "...", "duration": null, "severity": null, "onset": null, "details": null}
  ],
  "medical_history": ["..."],
  "medications": [
    {"name": "...", "dose": null, "frequency": null, "status": null}
  ],
  "allergies": [
    {"substance": "...", "reaction": null, "severity": null}
  ],
  "observations": ["..."],
  "diagnoses": ["..."],
  "plan": ["..."],
  "negative_findings": ["..."]
}

Do not include markdown code block syntax (```json), commentary, or extra keys. Output raw JSON only."""


def extract_clinical_facts_groq(transcript: Optional[str]) -> ClinicalExtraction:
    """
    Extracts structured clinical facts from a raw consultation transcript using Groq LLM.
    Validates output through ClinicalExtraction schema before returning.
    Preserves raw transcript as immutable; does not overwrite or translate.
    """
    if not transcript or not transcript.strip():
        raise ValueError("Cannot extract clinical information from an empty transcript.")

    cleaned_transcript = transcript.strip()
    if not settings.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not configured on the server.")

    payload = {
        "model": EXTRACTION_MODEL,
        "temperature": 0.0,
        "messages": [
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Extract all explicit clinical facts from this consultation transcript:\n\n{cleaned_transcript}\n\nJSON Output:",
            },
        ],
    }

    try:
        resp = None
        for attempt in range(4):
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(
                    GROQ_CHAT_URL,
                    headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"},
                    json=payload,
                )
            if resp.status_code == 429 and attempt < 3:
                wait_sec = 4.0 + (attempt * 2.0)
                try:
                    err_data = resp.json()
                    err_msg = err_data.get("error", {}).get("message", "")
                    match = re.search(r"try again in ([0-9.]+)s", err_msg)
                    if match:
                        wait_sec = float(match.group(1)) + 0.5
                except Exception:
                    pass
                time.sleep(wait_sec)
                continue
            break

        if resp is None or resp.status_code != 200:
            status_code = resp.status_code if resp else "unknown"
            text = resp.text if resp else "no response"
            raise RuntimeError(
                f"Groq clinical extraction request failed with status {status_code}: {text}"
            )

        data = resp.json()
        raw_content = data["choices"][0]["message"]["content"].strip()

        # Strip any markdown code formatting if the model wrapped output
        if raw_content.startswith("```"):
            raw_content = re.sub(r"^```(?:json)?\s*", "", raw_content)
            raw_content = re.sub(r"\s*```$", "", raw_content)
        raw_content = raw_content.strip()

        # Parse JSON
        parsed_json = json.loads(raw_content)

        # Context helpers for safety & fidelity normalization
        lower_transcript = cleaned_transcript.lower()
        has_explicit_hives = "hive" in lower_transcript or "urticaria" in lower_transcript
        has_explicit_severe = any(
            w in lower_transcript for w in ["severe", "critical", "गंभीर", "extreme"]
        )

        # Normalize lists if model returned strings instead of objects, enforcing fidelity
        normalized_symptoms = []
        for s in parsed_json.get("symptoms", []):
            if isinstance(s, str):
                normalized_symptoms.append(ExtractedSymptom(name=s))
            elif isinstance(s, dict) and "name" in s:
                # Fidelity check: conversational intensity (e.g., 'तेज बुखार') must not automatically become severity='severe'
                sev = s.get("severity")
                if sev and isinstance(sev, str) and sev.lower() in ("severe", "critical") and not has_explicit_severe:
                    s["severity"] = None
                    if not s.get("details") and ("तेज" in cleaned_transcript or "high" in lower_transcript):
                        s["details"] = "high fever" if "fever" in s.get("name", "").lower() else "high intensity"
                normalized_symptoms.append(ExtractedSymptom(**s))

        normalized_meds = []
        for m in parsed_json.get("medications", []):
            if isinstance(m, str):
                normalized_meds.append(ExtractedMedication(name=m))
            elif isinstance(m, dict) and "name" in m:
                normalized_meds.append(ExtractedMedication(**m))

        normalized_allergies = []
        for a in parsed_json.get("allergies", []):
            if isinstance(a, str):
                normalized_allergies.append(ExtractedAllergy(substance=a))
            elif isinstance(a, dict) and "substance" in a:
                # Fidelity check: Hindi 'चकत्ते' or general rash must never be over-specified to hives/urticaria
                reaction = a.get("reaction")
                if reaction and isinstance(reaction, str):
                    rx_lower = reaction.lower()
                    if ("hive" in rx_lower or "urticaria" in rx_lower) and not has_explicit_hives:
                        a["reaction"] = "rash"
                normalized_allergies.append(ExtractedAllergy(**a))

        extraction = ClinicalExtraction(
            symptoms=normalized_symptoms,
            medical_history=[str(item) for item in parsed_json.get("medical_history", []) if item],
            medications=normalized_meds,
            allergies=normalized_allergies,
            observations=[str(item) for item in parsed_json.get("observations", []) if item],
            diagnoses=[str(item) for item in parsed_json.get("diagnoses", []) if item],
            plan=[str(item) for item in parsed_json.get("plan", []) if item],
            negative_findings=[str(item) for item in parsed_json.get("negative_findings", []) if item],
            provenance="ai-extracted",
            extracted_at=utc_now(),
        )

        return extraction

    except json.JSONDecodeError as jde:
        raise ValueError(f"Failed to parse LLM extraction as valid JSON: {str(jde)}") from jde
    except httpx.RequestError as re_err:
        raise RuntimeError(f"Network error communicating with Groq API: {str(re_err)}") from re_err
    except Exception as exc:
        raise RuntimeError(f"Clinical information extraction failed: {str(exc)}") from exc
