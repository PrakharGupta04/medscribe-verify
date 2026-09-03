"""
llm_client.py

A thin, swappable wrapper around the Groq API. Every agent in this
project calls LLMClient.generate() and nothing else — no agent
imports the Groq SDK directly. If we ever switch providers, only
this file changes.
"""

from groq import Groq
from backend.config import GROQ_API_KEY, GROQ_MODEL


class LLMClient:
    """Minimal wrapper around Groq's chat completion API."""

    def __init__(self, model: str = None):
        if not GROQ_API_KEY:
            raise RuntimeError(
                "GROQ_API_KEY is missing. Run validate_config() before "
                "creating an LLMClient."
            )
        self._client = Groq(api_key=GROQ_API_KEY)
        self.model = model or GROQ_MODEL

    def generate(self, prompt: str, system_prompt: str = None,
                 temperature: float = 0.2, max_tokens: int = 1024) -> str:
        """
        Sends one prompt to the LLM and returns the plain text response.
        temperature is kept low by default — clinical note generation
        should be conservative, not creative.
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as e:
            error_name = type(e).__name__
            if "RateLimit" in error_name:
                raise RuntimeError(
                    "Groq free-tier rate limit hit. Wait a minute and "
                    "retry, or check console.groq.com/settings/limits"
                ) from e
            if "Authentication" in error_name or "Unauthorized" in str(e):
                raise RuntimeError(
                    "Groq rejected the API key. Check GROQ_API_KEY in .env."
                ) from e
            if "NotFound" in error_name or "model" in str(e).lower():
                raise RuntimeError(
                    f"Groq model '{self.model}' was not found — it may "
                    "have been deprecated. Check console.groq.com/docs/models "
                    "and update GROQ_MODEL in .env."
                ) from e
            raise RuntimeError(f"Groq API call failed: {e}") from e

        return response.choices[0].message.content.strip()