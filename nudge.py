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
    """Return a short (<~180 word) BDA-facing pre-call nudge for `profile`."""
    if not profile or not profile.strip():
        raise ValueError("profile is empty")

    references = _reference_block(profile)
    user = prompts.NUDGE_USER.format(profile=profile.strip(), verified_facts=references)
    user = f"{user}\n\n{_SALARY_GUARDRAIL}"
    return gemini_generate(prompts.NUDGE_SYSTEM, user).strip()
