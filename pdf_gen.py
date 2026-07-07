"""Post-call personalised PDF generator (build-order step 4).

Pipeline (structured input path — audio arrives in step 5):
    extract_questions(transcript)                    §6b -> {questions, lead_goal, tone_read}
    answer_questions(profile, questions, goal, tone) §6c -> {headline, opening, answers,
                                                             why_now, closing, accent_theme}
    render_pdf(content, accent_theme)                §7  -> WeasyPrint PDF bytes

HARD RULE: never invent curriculum / outcomes / salary / prices. Only state what's in
the grounded references; otherwise answer honestly and defer the exact detail to the
next call. Every section ladders toward the lead taking the ENTRANCE TEST.
"""

import html as _html
import json

import prompts
import grounding
from llm import gemini_generate

# Appended to the §6c prompt at call time (keeps prompts.py verbatim to SPEC).
_PDF_GUARDRAIL = (
    "GUARDRAIL (follow strictly):\n"
    "- Use ONLY facts from the verified/grounded references above. NEVER invent "
    "curriculum, modules, outcomes, salary/package numbers, placement %, or prices. "
    "If a needed detail isn't in the references, address the concern honestly and say "
    "the exact figure/detail will be confirmed on the next call.\n"
    "- No salary/placement guarantees or specific numbers — market figures in the "
    "references are general context, NOT Scaler outcomes.\n"
    "- Every section must build trust toward the lead taking the ENTRANCE TEST. "
    "'why_now' MUST frame the entrance test as the low-risk next step for THIS lead.\n"
    "- 'accent_theme' is ONE lowercase word derived from THIS lead's goal + tone "
    "(e.g. proof, roi, depth, mastery, security, reassurance, momentum) — never "
    "generic or random.\n"
    "- Personalise: headline, opening, and answer emphasis must reflect the lead's "
    "tone_read so the writing itself reads differently lead-to-lead."
)


# ---------------------------------------------------------------------------
# §6b — extract the lead's genuine open questions
# ---------------------------------------------------------------------------

def extract_questions(transcript: str) -> dict:
    """Return {questions[], lead_goal, tone_read} — only questions the LEAD
    actually raised and left unanswered."""
    if not transcript or not transcript.strip():
        raise ValueError("transcript is empty")
    user = prompts.EXTRACT_QUESTIONS_USER.format(transcript=transcript.strip())
    data = gemini_generate(prompts.EXTRACT_QUESTIONS_SYSTEM, user, json_mode=True)
    return {
        "questions": list(data.get("questions", [])),
        "lead_goal": data.get("lead_goal", ""),
        "tone_read": data.get("tone_read", ""),
    }


# ---------------------------------------------------------------------------
# §6c — grounded, personalised PDF content
# ---------------------------------------------------------------------------

def _evidence(profile: str, questions, lead_goal: str) -> str:
    """Assemble the allowed reference set: crisp verified facts + grounded
    scraped snippets relevant to the questions / goal / profile."""
    verified_lines = []
    for path, val in grounding._flatten_facts(grounding.load_facts()):
        s = str(val)
        if "TODO_SCRAPE" in s:
            continue
        verified_lines.append(f"- {path}: {s}")

    snippets, seen = [], set()
    for probe in list(questions) + [lead_goal, profile]:
        if not probe:
            continue
        for m in grounding.retrieve(probe).get("matches", []):
            if m["source"] == "scraped" and m["text"] not in seen:
                seen.add(m["text"])
                snippets.append(m["text"])

    block = "VERIFIED FACTS (source of truth — safe to state):\n" + "\n".join(verified_lines)
    if snippets:
        block += (
            "\n\nGROUNDED SCALER COPY (real text scraped from scaler.com — directional "
            "positioning/curriculum, NOT precise stats; never quote as guaranteed "
            "outcomes):\n" + "\n".join(f"- {s}" for s in snippets[:14])
        )
    return block


def answer_questions(profile: str, questions, lead_goal: str, tone_read: str) -> dict:
    """Return the grounded, personalised PDF content dict (§6c schema)."""
    evidence = _evidence(profile, questions, lead_goal)
    user = prompts.PDF_CONTENT_USER.format(
        profile=(profile or "").strip(),
        lead_goal=lead_goal,
        tone_read=tone_read,
        questions=json.dumps(list(questions), ensure_ascii=False),
        verified_facts=evidence,
    )
    user = f"{user}\n\n{_PDF_GUARDRAIL}"
    data = gemini_generate(prompts.PDF_CONTENT_SYSTEM, user, json_mode=True)
    return {
        "headline": data.get("headline", ""),
        "opening": data.get("opening", ""),
        "answers": list(data.get("answers", [])),
        "why_now": data.get("why_now", ""),
        "closing": data.get("closing", ""),
        "accent_theme": (data.get("accent_theme", "") or "").strip().lower(),
    }


def generate_pdf_content(profile: str, transcript: str):
    """Convenience: run §6b then §6c. Returns (questions_data, content)."""
    qdata = extract_questions(transcript)
    content = answer_questions(profile, qdata["questions"], qdata["lead_goal"], qdata["tone_read"])
    return qdata, content


# ---------------------------------------------------------------------------
# §7 — render (accent_theme drives colour + emphasis for visible divergence)
# ---------------------------------------------------------------------------

# Named themes -> {accent, light tint}. Unknown themes get a stable hashed hue.
_THEMES = {
    "proof":        {"accent": "#0f7b41", "light": "#e7f5ee"},
    "roi":          {"accent": "#0f7b41", "light": "#e7f5ee"},
    "results":      {"accent": "#0f7b41", "light": "#e7f5ee"},
    "growth":       {"accent": "#0f7b41", "light": "#e7f5ee"},
    "momentum":     {"accent": "#c2410c", "light": "#fdece4"},
    "depth":        {"accent": "#3538cd", "light": "#e9eafc"},
    "mastery":      {"accent": "#3538cd", "light": "#e9eafc"},
    "peer":         {"accent": "#3538cd", "light": "#e9eafc"},
    "rigor":        {"accent": "#3538cd", "light": "#e9eafc"},
    "security":     {"accent": "#6d28d9", "light": "#f0e9fd"},
    "reassurance":  {"accent": "#6d28d9", "light": "#f0e9fd"},
    "trust":        {"accent": "#6d28d9", "light": "#f0e9fd"},
    "affordability": {"accent": "#0e7490", "light": "#e3f4f8"},
    "stability":    {"accent": "#0e7490", "light": "#e3f4f8"},
}


def _palette(theme: str) -> dict:
    key = (theme or "").strip().lower()
    if key in _THEMES:
        return _THEMES[key]
    # Stable, distinct hue for any theme word we didn't hardcode.
    hue = (sum(ord(c) for c in key) * 47) % 360 if key else 210
    return {"accent": f"hsl({hue}, 62%, 40%)", "light": f"hsl({hue}, 60%, 95%)"}


def _build_html(content: dict, accent_theme: str = None) -> str:
    """Build the branded HTML (separated from PDF render so it's testable without
    WeasyPrint's native libs)."""
    theme = (accent_theme or content.get("accent_theme", "") or "").strip().lower()
    pal = _palette(theme)

    def esc(x):
        return _html.escape(str(x or "")).replace("\n", "<br>")

    answers_html = ""
    for a in content.get("answers", []):
        answers_html += (
            f'<div class="qa"><div class="q">{esc(a.get("question", ""))}</div>'
            f'<div class="a">{esc(a.get("response", ""))}</div></div>'
        )

    return f"""<html><head><meta charset="utf-8"><style>
  @page {{ size: A4; margin: 1.6cm 1.4cm; }}
  :root {{ --accent: {pal['accent']}; --accent-light: {pal['light']}; }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: 'Helvetica Neue', Arial, sans-serif; color: #1c1c1c;
          font-size: 12pt; line-height: 1.5; }}
  .brand {{ color: var(--accent); font-weight: 800; letter-spacing: 1px;
            font-size: 11pt; text-transform: uppercase; }}
  .badge {{ float: right; background: var(--accent-light); color: var(--accent);
            border-radius: 20px; padding: 3px 12px; font-size: 8.5pt;
            font-weight: 700; text-transform: uppercase; letter-spacing: 1px; }}
  h1 {{ color: var(--accent); font-size: 21pt; line-height: 1.2; margin: 10px 0 12px; }}
  .opening {{ font-size: 12.5pt; color: #333; border-left: 4px solid var(--accent);
              padding-left: 14px; margin: 14px 0 22px; }}
  .section-title {{ color: var(--accent); font-size: 11pt; text-transform: uppercase;
                    letter-spacing: 1.5px; font-weight: 700;
                    border-bottom: 2px solid var(--accent-light);
                    padding-bottom: 5px; margin: 26px 0 8px; }}
  .qa {{ margin: 14px 0; page-break-inside: avoid; }}
  .q {{ font-weight: 700; color: #111; }}
  .q::before {{ content: "Q  "; color: var(--accent); font-weight: 800; }}
  .a {{ margin-top: 4px; color: #333; }}
  .why-now {{ background: var(--accent-light); border-radius: 10px;
              padding: 16px 18px; margin: 24px 0; page-break-inside: avoid; }}
  .why-now .cta {{ color: var(--accent); font-weight: 800; text-transform: uppercase;
                   letter-spacing: 1px; font-size: 10pt; }}
  .closing {{ margin-top: 20px; }}
  .footer {{ margin-top: 30px; border-top: 1px solid #ddd; padding-top: 10px;
             color: #8a8a8a; font-size: 8.5pt; }}
</style></head><body>
  <span class="badge">{esc(theme)}</span>
  <div class="brand">Scaler</div>
  <h1>{esc(content.get('headline', ''))}</h1>
  <div class="opening">{esc(content.get('opening', ''))}</div>
  <div class="section-title">Your questions, answered</div>
  {answers_html}
  <div class="why-now"><span class="cta">Why now</span><br>{esc(content.get('why_now', ''))}</div>
  <div class="closing">{esc(content.get('closing', ''))}</div>
  <div class="footer">Personalised for you after our call &middot; Scaler &middot;
    Any detail marked for confirmation will be verified on our next conversation.</div>
</body></html>"""


def render_pdf(content: dict, accent_theme: str = None) -> bytes:
    """Render the branded template to PDF bytes via WeasyPrint.

    WeasyPrint is imported lazily so this module still imports on machines
    without the GTK native libs (e.g. local Windows); it renders on Streamlit
    Cloud where packages.txt provides them.
    """
    from weasyprint import HTML

    return HTML(string=_build_html(content, accent_theme)).write_pdf()


def draft_covering_message(qdata: dict, content: dict) -> str:
    """Short covering WhatsApp text that accompanies the PDF (editable in the gate)."""
    goal = (qdata.get("lead_goal") or "").strip().rstrip(".")
    goal_line = f" about {goal}" if goal else ""
    return (
        "Hi! Really enjoyed our conversation. I put together a short personalised "
        f"note answering your questions{goal_line}. Taking the entrance test is a "
        "low-pressure next step — the details are inside. — Team Scaler"
    )
