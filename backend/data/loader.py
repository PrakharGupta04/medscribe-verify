"""
loader.py

Loads local data files. For now, just the one sample transcript.
Week 4 will extend this to load MTS-Dialog — kept in its own file
so that change won't touch agent code at all.
"""

import os

_DATA_DIR = os.path.dirname(os.path.abspath(__file__))
_SAMPLE_PATH = os.path.join(_DATA_DIR, "sample_transcript.txt")


def load_sample_transcript() -> str:
    with open(_SAMPLE_PATH, "r", encoding="utf-8") as f:
        return f.read().strip()