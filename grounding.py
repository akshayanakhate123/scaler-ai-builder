"""Grounding / anti-hallucination layer.

STUB — build order step 2. Not implemented in step 1.
See SPEC.md section 4. verified_facts.json is the only source of Scaler-specific
claims; nothing may be stated that isn't verified.
"""

import json
import os

_FACTS_PATH = os.path.join(os.path.dirname(__file__), "verified_facts.json")


def load_facts() -> dict:
    """Load the seed verified facts. (Already usable in step 1.)"""
    with open(_FACTS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def scrape_scaler() -> dict:
    """TODO(step 2): fetch a few scaler.com program pages, BeautifulSoup out
    visible curriculum/outcome text, cache to disk. Skip thin/JS-rendered pages
    rather than inventing anything."""
    raise NotImplementedError("scrape_scaler is a step-2 stub — not built yet.")


def retrieve(topic: str):
    """TODO(step 2): return only matched verified snippets for a topic."""
    raise NotImplementedError("retrieve is a step-2 stub — not built yet.")
