"""
run_baseline.py

The Week 1 end-to-end proof: sample transcript -> baseline agent ->
Groq LLM -> printed clinical note.

Run with:
    python -m backend.run_baseline
"""

from backend.config import validate_config
from backend.data.loader import load_sample_transcript
from backend.agents.baseline_agent import generate_baseline_note


def main():
    print("Validating configuration...")
    validate_config()
    print("Config OK.\n")

    print("Loading sample transcript...")
    transcript = load_sample_transcript()
    print(f"Transcript loaded ({len(transcript)} characters).\n")

    print("Calling Groq LLM to generate baseline SOAP note...\n")
    try:
        note = generate_baseline_note(transcript)
    except (RuntimeError, ValueError) as e:
        print(f"FAILED: {e}")
        return

    print("=" * 60)
    print("GENERATED CLINICAL NOTE (baseline, unverified)")
    print("=" * 60)
    print(note)
    print("=" * 60)


if __name__ == "__main__":
    main()