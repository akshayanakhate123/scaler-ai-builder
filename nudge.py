"""Pre-call nudge generation (BDA-facing, no approval gate) — SPEC §6a.

generate_nudge(profile) assembles a grounded reference block (verified facts +
profile-relevant scraped snippets), then calls the LLM (Gemini, Groq fallback)
with the verbatim §6a prompt plus an anti-hallucination guardrail for
salary/placement (we have NO verified Scaler outcome numbers).
"""

import prompts
import grounding
from llm import gemini_generate

# We have no verified Scaler salary/placement stats. This guardrail is appended
# at call time so prompts.NUDGE_SYSTEM stays verbatim to SPEC.
_SALARY_GUARDRAIL = (
    "GUARDRAIL — HONEST HANDLING: There are NO verified Scaler salary, package, "
    "hike, or placement statistics available. For any salary/placement objection, "
    "do NOT state, promise, or imply specific numbers or guarantees. Handle it "
    "honestly: point to the structured placement support (resume review, mock "
    "interviews, placement assistance) and that exact, verified outcomes can be "
    "shared on the call. Any market/industry salary figures in the references are "
    "general context, NOT Scaler outcomes — never cite them as what Scaler delivers."
)

# Length + tag discipline. Appended at call time so prompts.NUDGE_SYSTEM stays
# verbatim to SPEC.
_STYLE_RULES = (
    "STYLE RULES (follow strictly):\n"
    "- HARD LENGTH CAP: the entire nudge MUST be under 150 words. Write at "
    "scannable phone-brief density — terse fragments, not prose sentences.\n"
    "- CONFIDENCE TAGS: use ONLY these three, spelled exactly: [fact], [inferred], "
    "[missing]. Do NOT invent any other tag (no [grounded], [grounded in copy], "
    "etc.). Anything drawn from Scaler's website copy counts as [fact]. Use "
    "[inferred] for reasoned guesses about the lead. Use [missing] wherever the "
    "profile lacks the data — e.g. if no LinkedIn / skills / experience detail is "
    "given, flag those [missing]; never silently assume them.\n"
    "- MANDATORY [missing]: if the profile provides no LinkedIn, no listed skills, "
    "or no concrete work experience, you MUST include at least one [missing] tag "
    "naming that gap (e.g. 'technical depth unknown [missing]'). Do NOT dress an "
    "unknown up as [inferred] or [fact]."
)

_WORD_LIMIT = 150
_REGEN_THRESHOLD = 170  # regenerate once if the first draft exceeds this


def _reference_block(profile: str) -> str:
    """Assemble the allowed reference set: crisp verified facts + grounded,
    profile-relevant scraped snippets. Nothing beyond this may be stated."""
    verified_lines = []
    for path, val in grounding._flatten_facts(grounding.load_facts()):
        s = str(val)
        if "TODO_SCRAPE" in s:  # unresolved placeholders are NOT facts
            continue
        verified_lines.append(f"- {path}: {s}")

    block = "VERIFIED FACTS (source of truth — safe to state):\n" + "\n".join(verified_lines)

    result = grounding.retrieve(profile)
    scraped = [m["text"] for m in result.get("matches", []) if m["source"] == "scraped"]
    if scraped:
        block += (
            "\n\nGROUNDED SCALER COPY (real text scraped from scaler.com — directional "
            "positioning/curriculum, NOT precise stats; do not quote as guaranteed "
            "outcomes):\n" + "\n".join(f"- {s}" for s in scraped[:10])
        )
    return block


def generate_nudge(profile: str) -> str:
    """Return a tight (<150 word) BDA-facing pre-call nudge for `profile`.

    If the first draft runs long (> ~170 words), regenerate once with an
    explicit compress instruction.
    """
    if not profile or not profile.strip():
        raise ValueError("profile is empty")

    references = _reference_block(profile)
    user = prompts.NUDGE_USER.format(profile=profile.strip(), verified_facts=references)
    user = f"{user}\n\n{_SALARY_GUARDRAIL}\n\n{_STYLE_RULES}"

    text = gemini_generate(prompts.NUDGE_SYSTEM, user).strip()

    if len(text.split()) > _REGEN_THRESHOLD:
        compress = (
            f"{user}\n\nA prior draft ran too long ({len(text.split())} words). "
            f"Produce the SAME nudge compressed to UNDER {_WORD_LIMIT} words — cut "
            "filler, keep every section, keep only [fact]/[inferred]/[missing] tags. "
            f"Prior draft:\n{text}"
        )
        text = gemini_generate(prompts.NUDGE_SYSTEM, compress).strip()

    return text
