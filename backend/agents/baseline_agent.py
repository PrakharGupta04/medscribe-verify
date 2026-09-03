"""
baseline_agent.py

The "naive" baseline: transcript -> one LLM call -> clinical note.
Every later agent (extraction, SOAP drafting, verifier) is measured
against this. If the fuller pipeline can't beat this, the project's
core claim doesn't hold — so this has to exist and work first.
"""

from backend.llm_client import LLMClient

SYSTEM_PROMPT = (
    "You are a clinical documentation assistant. You write concise, "
    "accurate SOAP-format clinical notes based only on what was "
    "explicitly said in a doctor-patient conversation transcript. "
    "Do not invent symptoms, findings, vitals, or medications that "
    "are not present in the transcript."
)


def build_baseline_prompt(transcript: str) -> str:
    """
    Pure function: builds prompt text from a transcript. Kept
    separate from the API call so it can be unit-tested without
    network access or an API key.
    """
    return (
        "Read the following doctor-patient conversation transcript and "
        "write a clinical note in SOAP format (Subjective, Objective, "
        "Assessment, Plan).\n\n"
        f"Transcript:\n{transcript}\n\n"
        "SOAP Note:"
    )


def generate_baseline_note(transcript: str, client: LLMClient = None) -> str:
    """
    Generates a SOAP note directly from a transcript with a single
    LLM call and no verification — the baseline the rest of the
    pipeline will be measured against starting Week 2.
    """
    if not transcript or not transcript.strip():
        raise ValueError("transcript must be a non-empty string")

    if client is None:
        client = LLMClient()

    prompt = build_baseline_prompt(transcript)
    return client.generate(prompt, system_prompt=SYSTEM_PROMPT)