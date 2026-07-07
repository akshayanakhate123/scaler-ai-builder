"""Personalised follow-up PDF generation.

STUB — build order step 4 (the 30% personalisation dimension). Not implemented
in step 1. See SPEC.md sections 6b, 6c, and 7.

Step 1 generates its trivial test PDF inline in app.py; this module is where the
real, per-lead branded PDF pipeline will live.
"""


def extract_questions(transcript: str) -> dict:
    """TODO(step 4): prompts 6b — pull the lead's genuine open questions."""
    raise NotImplementedError("extract_questions is a step-4 stub — not built yet.")


def answer_questions(profile: str, questions, verified_facts) -> dict:
    """TODO(step 4): prompts 6c — grounded, personalised PDF content."""
    raise NotImplementedError("answer_questions is a step-4 stub — not built yet.")


def render_pdf(content: dict, accent_theme: str) -> bytes:
    """TODO(step 4): render the branded HTML template with a per-lead accent
    colour (driven by accent_theme) to PDF bytes via WeasyPrint."""
    raise NotImplementedError("render_pdf is a step-4 stub — not built yet.")
