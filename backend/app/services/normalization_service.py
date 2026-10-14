import re
from typing import Optional
import httpx

from backend.app.core.config import settings

GROQ_AUDIO_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
TRANSLATION_MODEL = "qwen/qwen3.8-27b"
WHISPER_MODEL = "whisper-large-v3"

# Common Hinglish markers, Urdu/Arabic script, and Devanagari Unicode range
DEVANAGARI_REGEX = re.compile(r"[\u0900-\u097F]")
URDU_ARABIC_REGEX = re.compile(r"[\u0600-\u06FF]")
HINGLISH_PROMPT = "Patient clinical intake speaking in Hinglish (Roman Hindi) or English: Mujhe bukhar hai, sar dard, dawai, allergy, koi medicine nahi le raha hoon, paracetamol, fever."
HINGLISH_KEYWORDS = {
    "hai", "hain", "mujhe", "mera", "meri", "mere", "ko", "se", "me", "mein",
    "bukhar", "dard", "gale", "sar", "sir", "pet", "ulti", "chakkar", "khansi",
    "dawai", "le", "raha", "rahi", "tha", "thi", "bahut", "thoda", "kam",
    "din", "hafte", "kuch", "nahi", "hota", "hoti", "pehle", "baad", "pe"
}


def is_hindi_or_hinglish(text: str) -> bool:
    if not text:
        return False
    if DEVANAGARI_REGEX.search(text):
        return True
    # Check lowercase tokens for Hinglish indicators
    tokens = set(re.findall(r"[a-zA-Z]+", text.lower()))
    matches = tokens.intersection(HINGLISH_KEYWORDS)
    return len(matches) >= 1


def normalize_to_clinical_english(text: Optional[str]) -> str:
    """
    Converts Hindi or Hinglish patient input into clean clinical English.
    If text is already English, it returns the input unchanged.
    Never raises an exception; falls back gracefully to original text.
    """
    if not text or not text.strip():
        return ""

    raw_text = text.strip()

    # Fast path: If purely ASCII and no Hinglish markers, return original text as-is
    if not is_hindi_or_hinglish(raw_text):
        return raw_text

    if not settings.GROQ_API_KEY:
        return raw_text

    try:
        payload = {
            "model": TRANSLATION_MODEL,
            "temperature": 0.1,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a medical intake translation assistant. Translate patient-reported "
                        "text from Hindi (Devanagari) or Hinglish (Romanized Hindi) into clean, "
                        "standard clinical English. If the input is already in English, output it unchanged. "
                        "Do not add medical advice, diagnoses, conversational filler, markdown formatting, "
                        "or quotes. Output ONLY the clean clinical English translation."
                    ),
                },
                {"role": "user", "content": raw_text},
            ],
        }
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(
                GROQ_CHAT_URL,
                headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"},
                json=payload,
            )
            if resp.status_code == 200:
                data = resp.json()
                translated = data["choices"][0]["message"]["content"].strip()
                # Clean any accidental outer quotes if model wrapped output
                if (translated.startswith('"') and translated.endswith('"')) or (
                    translated.startswith("'") and translated.endswith("'")
                ):
                    translated = translated[1:-1].strip()
                return translated if translated else raw_text
    except Exception:
        # Fall back to raw text on any communication failure
        return raw_text

    return raw_text


def transcribe_audio_groq(
    audio_bytes: bytes, filename: str = "audio.webm", language: Optional[str] = None
) -> str:
    """
    Transcribes patient voice speech in English, Hindi, or Hinglish using Groq Whisper.
    Preserves the language and script actually spoken by the patient:
    - English speech -> English text (Latin script)
    - Hindi speech -> Hindi in Devanagari script
    - Hinglish speech -> Hinglish (Roman Hindi) in Latin script (suppressing Urdu/Arabic script)
    Never translates the speech into English at this stage so the patient can review what they said.
    """
    if not settings.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not configured on the server.")

    # Determine proper MIME type matching the audio container
    ext = (filename.lower().split(".")[-1]) if "." in filename else "webm"
    mime_map = {
        "webm": "audio/webm",
        "mp4": "audio/mp4",
        "m4a": "audio/m4a",
        "ogg": "audio/ogg",
        "wav": "audio/wav",
    }
    content_type = mime_map.get(ext, "audio/webm")

    if not audio_bytes or len(audio_bytes) < 400:
        return ""

    def _call_whisper(
        lang_param: Optional[str] = None,
        prompt_param: Optional[str] = None,
    ) -> tuple[str, str]:
        files = {"file": (filename, audio_bytes, content_type)}
        data = {
            "model": WHISPER_MODEL,
            "response_format": "verbose_json",
            "temperature": "0.0",
        }
        if lang_param and lang_param.lower() in {"en", "hi"}:
            data["language"] = lang_param.lower()
        if prompt_param:
            data["prompt"] = prompt_param

        with httpx.Client(timeout=25.0) as client:
            resp = client.post(
                GROQ_AUDIO_URL,
                headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"},
                files=files,
                data=data,
            )
            if resp.status_code != 200:
                if resp.status_code == 400 and "audio_too_short" in resp.text:
                    return "", ""
                raise RuntimeError(
                    f"Groq Whisper transcription failed ({resp.status_code}): {resp.text}"
                )
            result = resp.json()
            raw_text = result.get("text", "").strip()
            detected_lang = (result.get("language") or "").lower()
            print(f"[WHISPER_DEBUG] Groq status={resp.status_code}, raw_text='{raw_text}', detected_lang='{detected_lang}'", flush=True)
            return raw_text, detected_lang

    def _filter_hallucinations(raw_text: str) -> str:
        if not raw_text:
            return ""
        # Filter known silent-audio artifacts
        hallucination_triggers = {
            "झाल", "झाला", "झालं", "झाल झाल", "झाला झाला", "झाल झाल झाल",
            "सब्सक्राइब", "Thanks for watching!", "Thank you for watching!",
            "Subtitles by the Amara.org community",
        }
        cleaned = raw_text.strip().rstrip(".")
        if cleaned in hallucination_triggers:
            return ""

        tokens = [t.lower() for t in re.findall(r"[\w]+", raw_text)]
        # Repetitive single-word hallucination loops on silence
        if tokens and all(t in {"झाल", "झाला", "झालं"} for t in tokens):
            return ""
        if len(tokens) <= 2 and all(t in {"thank", "you", "thanks"} for t in tokens) and len(raw_text) < 15:
            return ""

        return raw_text

    req_lang = (language or "").strip().lower()

    # Step 1: Execute primary transcription based on context and language detection
    if req_lang == "hinglish":
        # Hinglish context: pass language="en" with Romanized Hindi prompt to enforce Latin script.
        # Whisper constrained to English token space transcribes phonetically in Latin alphabet
        # without converting to Devanagari or Urdu script.
        text, detected_lang = _call_whisper(lang_param="en", prompt_param=HINGLISH_PROMPT)
    else:
        # Multilingual auto-detection: allows a patient with Hindi or English UI to speak either language
        text, detected_lang = _call_whisper(lang_param=None)

    text = _filter_hallucinations(text)

    # Step 2: Handle Urdu script / language misclassification
    # Whisper frequently misclassifies Hindustani speech as "urdu" and outputs Arabic script ([\u0600-\u06FF]).
    # When this occurs:
    # - If UI is Hinglish: re-transcribe with language="en" and Hinglish prompt to ensure Latin script
    # - Otherwise (Hindi or general): re-transcribe with language="hi" to produce clean Devanagari Hindi.
    if URDU_ARABIC_REGEX.search(text) or (detected_lang in {"urdu", "ur"} and req_lang != "hinglish"):
        if req_lang == "hinglish":
            text, _ = _call_whisper(lang_param="en", prompt_param=HINGLISH_PROMPT)
            text = _filter_hallucinations(text)
        else:
            text, _ = _call_whisper(lang_param="hi")
            text = _filter_hallucinations(text)

    # Step 3: If patient selected Hindi UI and spoke Hindi, ensure Devanagari script
    # (in case Whisper transcribed Hindi phonetically or tagged as Hindi without Devanagari)
    if req_lang == "hi" and detected_lang in {"hindi", "hi"} and not DEVANAGARI_REGEX.search(text):
        retry_text, _ = _call_whisper(lang_param="hi")
        retry_text = _filter_hallucinations(retry_text)
        if retry_text:
            text = retry_text

    return text
