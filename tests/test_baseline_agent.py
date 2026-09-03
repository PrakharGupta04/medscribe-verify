"""
test_baseline_agent.py

Tests the network-free parts of the baseline agent only — the
prompt builder and input validation. Deliberately does NOT call
the real Groq API, so these run instantly, free, with no API key
required.
"""

import unittest
from backend.agents.baseline_agent import build_baseline_prompt, generate_baseline_note


class TestBaselinePrompt(unittest.TestCase):

    def test_prompt_contains_transcript(self):
        transcript = "Doctor: How are you feeling?"
        prompt = build_baseline_prompt(transcript)
        self.assertIn(transcript, prompt)

    def test_prompt_asks_for_soap_format(self):
        prompt = build_baseline_prompt("some transcript")
        self.assertIn("SOAP", prompt)


class TestBaselineNoteValidation(unittest.TestCase):

    def test_empty_transcript_raises(self):
        with self.assertRaises(ValueError):
            generate_baseline_note("")

    def test_whitespace_only_transcript_raises(self):
        with self.assertRaises(ValueError):
            generate_baseline_note("   ")


if __name__ == "__main__":
    unittest.main()