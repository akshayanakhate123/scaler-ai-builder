"""LLM helper: Gemini 2.5 Flash primary, Groq llama-3.3-70b-versatile fallback.

Implemented per SPEC.md section 5. Not exercised by step 1 (nudge/PDF are later
steps), but it's a small core helper so it lives here as foundation.
"""

import json

import streamlit as st

GEMINI_MODEL = "gemini-2.5-flash"
GROQ_MODEL = "llama-3.3-70b-versatile"


def _strip_json_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t
        if t.endswith("```"):
            t = t[: -3]
        if t.lstrip().startswith("json"):
            t = t.lstrip()[4:]
    return t.strip()


def _gemini(system: str, user: str) -> str:
    import google.generativeai as genai

    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel(GEMINI_MODEL, system_instruction=system)
    resp = model.generate_content(user)
    return resp.text


def _groq(system: str, user: str) -> str:
    from groq import Groq

    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
    resp = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return resp.choices[0].message.content


def gemini_generate(system: str, user: str, json_mode: bool = False):
    """Call Gemini; on any error retry once, then fall back to Groq.

    If json_mode, appends a JSON-only instruction, strips ```json fences, and
    returns the parsed object. Otherwise returns the raw string.
    """
    if json_mode:
        system = system + "\n\nReturn ONLY valid JSON, no markdown fences."

    text = None
    for attempt in range(2):  # try Gemini twice
        try:
            text = _gemini(system, user)
            break
        except Exception:  # noqa: BLE001
            if attempt == 1:
                text = None

    if text is None:
        # Fall back to Groq.
        text = _groq(system, user)

    if json_mode:
        return json.loads(_strip_json_fences(text))
    return text
