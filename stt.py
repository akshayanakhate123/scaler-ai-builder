"""Speech-to-text via Groq whisper-large-v3-turbo (build-order step 5).

The audio path only produces a transcript string; that string then flows into the
SAME extract_questions -> answer_questions -> render_pdf pipeline the structured
path uses. No extraction/answer/render logic is duplicated here.
"""

import streamlit as st
from groq import Groq

_MODEL = "whisper-large-v3-turbo"
MAX_BYTES = 25 * 1024 * 1024  # Groq free-tier upload cap (25 MB)


class TranscriptionError(Exception):
    """Raised on a transcription failure, with a message safe to show in the UI."""


def transcribe(audio_bytes: bytes, filename: str) -> str:
    """Transcribe audio bytes to a plain English transcript string.

    Raises TranscriptionError (never crashes the app) if the file is empty,
    exceeds Groq's 25 MB limit, the API call fails, or nothing is transcribed.
    """
    if not audio_bytes:
        raise TranscriptionError("No audio provided.")

    if len(audio_bytes) > MAX_BYTES:
        mb = len(audio_bytes) / (1024 * 1024)
        raise TranscriptionError(
            f"Audio is {mb:.1f} MB — over Groq's 25 MB free-tier limit. "
            "Upload a shorter or compressed file (e.g. mono mp3 at 16 kHz)."
        )

    try:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"])
        result = client.audio.transcriptions.create(
            file=(filename, audio_bytes),
            model=_MODEL,
            response_format="text",
            language="en",
        )
    except Exception as e:  # noqa: BLE001 — surface a clean message to the UI
        raise TranscriptionError(f"Transcription failed: {e}") from e

    # response_format="text" returns the raw string; be defensive about SDK shape.
    text = result if isinstance(result, str) else getattr(result, "text", str(result))
    text = (text or "").strip()
    if not text:
        raise TranscriptionError("Transcription returned empty text.")
    return text
