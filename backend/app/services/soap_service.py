import json
import re
import time
from datetime import datetime, timezone
from typing import Optional
import httpx

from backend.app.core.config import settings
from backend.app.schemas.consultation import ClinicalExtraction, SoapDraft

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
SOAP_MODEL = "qwen/qwen3.8-27b"
SOAP_MAX_TOKENS = 750

SENTINEL_OBJECTIVE = "Not documented."
SENTINEL_ASSESSMENT = "Not explicitly documented."
SENTINEL_PLAN = "Not documented."


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


SOAP_SYSTEM_PROMPT = """You are an expert, conservative clinical documentation assistant.
Your task is to generate an AI-assisted SOAP draft note from the doctor-patient consultation transcript and validated extracted clinical facts.

CRITICAL CLINICAL FIDELITY & SAFETY RULES:
1. OUTPUT LANGUAGE: Regardless of whether the raw transcript contains English, Hindi, or Hinglish, the generated SOAP draft MUST be written in clear, standard English clinical terminology.
2. S = SUBJECTIVE:
   - Summarize ONLY patient-reported information: chief complaint, symptoms (with duration, onset, severity, and qualifiers), relevant medical history, patient-reported current medications, allergies, and explicitly denied symptoms / negative findings.
   - If the patient expressed a personal suspicion or self-diagnosis (e.g., "I think I have malaria", "I feel like it might be pneumonia"), keep it strictly within the Subjective section as patient-reported context. It must NEVER be placed in the Assessment.
3. O = OBJECTIVE:
   - Include ONLY explicitly documented physical exam findings, vital signs (BP, HR, RR, temp, SpO2), labs, imaging, or measurements stated in the consultation transcript or extracted facts.
   - DO NOT INVENT or assume any vital signs or physical exam findings.
   - If no objective findings or measurements are explicitly documented, output EXACTLY:
     "Not documented."
4. A = ASSESSMENT:
   - Include ONLY a diagnosis or clinical impression explicitly authored or stated by the clinician/doctor in the consultation transcript or extracted facts.
   - DO NOT INFER, speculate, or deduce a diagnosis from symptoms.
   - A patient's self-diagnosis or suspicion MUST NOT become the Assessment.
   - If no clinician diagnosis or impression is explicitly stated, output EXACTLY:
     "Not explicitly documented."
5. P = PLAN:
   - Include ONLY an explicit plan, prescription, diagnostic test, investigation, referral, follow-up, or instruction stated by the clinician in the consultation.
   - DO NOT INVENT medications, treatments, tests, or follow-up.
   - If no clinician plan or next step is explicitly documented, output EXACTLY:
     "Not documented."
6. The note is an UNVERIFIED WORKING DRAFT. Do not include physician sign-offs or claims of final approval.
7. CONCISENESS: Keep each section concise, factual, and strictly under 100 words per section. Avoid unnecessary preamble or conversational filler.

Return ONLY a valid JSON object matching this exact schema:
{
  "subjective": "...",
  "objective": "...",
  "assessment": "...",
  "plan": "..."
}

Do not include markdown code block syntax (```json), commentary, or extra keys."""


def generate_soap_draft_groq(
    transcript: str,
    clinical_data: ClinicalExtraction,
) -> SoapDraft:
    """
    Generates a structured SOAP draft note using Groq LLM from the raw transcript
    and the validated Phase 2.3 clinical extraction.
    Enforces strict sentinel values and non-hallucination rules.
    """
    if not transcript or not transcript.strip():
        raise ValueError("Cannot generate SOAP draft from an empty transcript.")

    cleaned_transcript = transcript.strip()
    if not settings.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not configured on the server.")

    clinical_summary = json.dumps(clinical_data.model_dump(mode="json"), indent=2)

    user_prompt = (
        f"Generate a strict, conservative SOAP draft note based ONLY on the consultation transcript "
        f"and structured clinical extraction provided below.\n\n"
        f"--- RAW TRANSCRIPT ---\n{cleaned_transcript}\n\n"
        f"--- STRUCTURED CLINICAL EXTRACTION ---\n{clinical_summary}\n\n"
        f"JSON Output:"
    )

    payload = {
        "model": SOAP_MODEL,
        "temperature": 0.0,
        "max_tokens": SOAP_MAX_TOKENS,
        "messages": [
            {"role": "system", "content": SOAP_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
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
                f"Groq SOAP generation request failed with status {status_code}: {text}"
            )

        data = resp.json()
        raw_content = data["choices"][0]["message"]["content"].strip()

        # Strip markdown syntax if wrapped
        if raw_content.startswith("```"):
            raw_content = re.sub(r"^```(?:json)?\s*", "", raw_content)
            raw_content = re.sub(r"\s*```$", "", raw_content)
        raw_content = raw_content.strip()

        parsed_json = json.loads(raw_content)

        subjective = (parsed_json.get("subjective") or "").strip()
        objective = (parsed_json.get("objective") or "").strip()
        assessment = (parsed_json.get("assessment") or "").strip()
        plan = (parsed_json.get("plan") or "").strip()

        # Normalization and sentinel enforcement for Objective
        obj_lower = objective.lower()
        if (
            not objective
            or "none" in obj_lower
            or "n/a" in obj_lower
            or "not documented" in obj_lower
            or len(clinical_data.observations) == 0
        ):
            has_explicit_exam = any(
                term in cleaned_transcript.lower()
                for term in ["blood pressure", "bp", "pulse", "heart rate", "exam:", "examination:", "temperature:"]
            )
            if not has_explicit_exam and len(clinical_data.observations) == 0:
                objective = SENTINEL_OBJECTIVE

        # Normalization and sentinel enforcement for Assessment
        ass_lower = assessment.lower()
        if (
            not assessment
            or "none" in ass_lower
            or "n/a" in ass_lower
            or "not explicitly documented" in ass_lower
            or len(clinical_data.diagnoses) == 0
        ):
            has_explicit_diagnosis = len(clinical_data.diagnoses) > 0 or any(
                phrase in cleaned_transcript.lower()
                for phrase in ["diagnos", "impression:", "assessment:", "i diagnose you with", "you have acute"]
            )
            if not has_explicit_diagnosis:
                assessment = SENTINEL_ASSESSMENT

        # Normalization and sentinel enforcement for Plan
        plan_lower = plan.lower()
        if (
            not plan
            or "none" in plan_lower
            or "n/a" in plan_lower
            or "not documented" in plan_lower
            or len(clinical_data.plan) == 0
        ):
            has_explicit_plan = len(clinical_data.plan) > 0 or any(
                phrase in cleaned_transcript.lower()
                for phrase in ["prescribe", "take this", "plan:", "treatment:", "follow-up in", "order a", "blood test"]
            )
            if not has_explicit_plan:
                plan = SENTINEL_PLAN

        now = utc_now()
        return SoapDraft(
            subjective=subjective if subjective else "Patient-reported symptoms and history as documented.",
            objective=objective if objective else SENTINEL_OBJECTIVE,
            assessment=assessment if assessment else SENTINEL_ASSESSMENT,
            plan=plan if plan else SENTINEL_PLAN,
            provenance="ai-generated-draft-unverified",
            generated_at=now,
            updated_at=now,
        )

    except json.JSONDecodeError as jde:
        raise ValueError(f"Failed to parse LLM SOAP response as valid JSON: {str(jde)}") from jde
    except httpx.RequestError as re_err:
        raise RuntimeError(f"Network error communicating with Groq API: {str(re_err)}") from re_err
    except Exception as exc:
        raise RuntimeError(f"SOAP draft generation failed: {str(exc)}") from exc
