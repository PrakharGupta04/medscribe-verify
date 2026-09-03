"""
config.py

Loads environment variables and validates required configuration
before any agent or API call is attempted. Every other file in this
project reads its configuration from here — nothing is hardcoded
anywhere else, so swapping providers or models later means changing
this one file.
"""

import os
from dotenv import load_dotenv

load_dotenv()  # reads the .env file in the project root

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# openai/gpt-oss-20b is Groq's current recommended free-tier model
# (as of Sept 2026). llama-3.1-8b-instant and llama-3.3-70b-versatile
# were deprecated by Groq and are no longer served. If this model is
# ever deprecated too, check https://console.groq.com/docs/deprecations
# and change GROQ_MODEL in .env — no code changes needed.
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")


def validate_config():
    """
    Call this once at startup. Raises a clear error immediately if
    required config is missing, instead of a vague API error later.
    """
    if not GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is missing. Create a .env file in the project "
            "root with a line like: GROQ_API_KEY=your_key_here"
        )
    return True