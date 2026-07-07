"""Grounding / anti-hallucination layer (build-order step 2).

verified_facts.json is the ONLY source of truth for Scaler-specific claims.
scrape_scaler() may ENRICH a separate cache (scraped_cache.json), but it never
writes to verified_facts.json and never invents: pages that are thin, JS-rendered,
time out, or error are skipped and logged. Promoting a scraped snippet into
verified_facts.json is a deliberate, by-hand decision — not automatic.

retrieve(topic) returns only matched verified/cached snippets. If nothing
verified matches, it returns a clear "not verified" marker so downstream
generation says "the team can confirm on the call" instead of fabricating.
"""

import json
import os
import re
import time

import requests
from bs4 import BeautifulSoup

_HERE = os.path.dirname(__file__)
_FACTS_PATH = os.path.join(_HERE, "verified_facts.json")
_CACHE_PATH = os.path.join(_HERE, "scraped_cache.json")

# Real scaler.com program pages, keyed to verified_facts.json program ids.
# `_home` is a fallback source of general, still-verifiable copy.
SCRAPE_URLS = {
    "scaler_academy": "https://www.scaler.com/academy/",
    "data_science_ml": "https://www.scaler.com/data-science-course/",
    "devops_cloud": "https://www.scaler.com/devops-course/",
    "ai_engineering": "https://www.scaler.com/artificial-intelligence-course/",
    "_home": "https://www.scaler.com/",
}

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# A page whose total visible text is below this is treated as thin/JS-rendered.
_MIN_PAGE_TEXT = 500
# Keep only chunks in this size band as candidate "snippets".
_MIN_CHUNK, _MAX_CHUNK = 25, 320

# Keywords that mark a chunk as curriculum/outcome-relevant (what we actually want).
_RELEVANT_KEYWORDS = (
    "curriculum", "syllabus", "module", "course", "program", "learn", "topics",
    "project", "mentor", "duration", "month", "week", "outcome", "placement",
    "salary", "hike", "ctc", "package", "alumni", "career", "job", "hiring",
    "fee", "emi", "scholarship", "financing", "cost", "price", "entrance",
    "eligibility", "experience", "beginner", "software engineering", "data science",
    "machine learning", "devops", "cloud", "ai ", "gen ai", "certificate",
)


# ---------------------------------------------------------------------------
# Verified facts (source of truth)
# ---------------------------------------------------------------------------

def load_facts() -> dict:
    """Read verified_facts.json — the only sanctioned source of Scaler claims."""
    with open(_FACTS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_cache() -> dict:
    """Read scraped_cache.json if present; missing cache is fine (returns {})."""
    if not os.path.exists(_CACHE_PATH):
        return {}
    try:
        with open(_CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


# ---------------------------------------------------------------------------
# Scraping
# ---------------------------------------------------------------------------

def _extract_chunks(html):
    """Pull structured visible text chunks (headings, list items, paragraphs).

    Accepts raw bytes so BeautifulSoup can detect the page's real charset from
    its <meta> tag (avoids mojibake from requests' fallback encoding).
    """
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "head", "template"]):
        tag.decompose()
    chunks, seen = [], set()
    for el in soup.find_all(["h1", "h2", "h3", "h4", "li", "p"]):
        text = " ".join(el.get_text(separator=" ", strip=True).split())
        if text and text not in seen:
            seen.add(text)
            chunks.append(text)
    return chunks


def _relevant_snippets(chunks):
    """Keep reasonably-sized chunks that mention curriculum/outcome keywords."""
    out = []
    for c in chunks:
        if not (_MIN_CHUNK <= len(c) <= _MAX_CHUNK):
            continue
        low = c.lower()
        if any(kw in low for kw in _RELEVANT_KEYWORDS):
            out.append(c)
    return out


def scrape_scaler(urls=None, timeout=15) -> dict:
    """Fetch program pages, extract visible curriculum/outcome text, cache it.

    Writes scraped_cache.json (never verified_facts.json). Returns a report of
    which URLs succeeded and which were skipped (with the reason). Never raises
    on a bad page and never fabricates content.
    """
    urls = urls or SCRAPE_URLS
    cache, report = {}, {"succeeded": [], "skipped": []}

    for program, url in urls.items():
        try:
            resp = requests.get(url, headers=_HEADERS, timeout=timeout)
        except requests.RequestException as e:
            report["skipped"].append(
                {"program": program, "url": url, "reason": f"request error: {e.__class__.__name__}"}
            )
            continue

        if resp.status_code != 200:
            report["skipped"].append(
                {"program": program, "url": url, "reason": f"HTTP {resp.status_code}"}
            )
            continue

        chunks = _extract_chunks(resp.content)  # bytes -> bs4 detects charset
        total_text = sum(len(c) for c in chunks)
        if total_text < _MIN_PAGE_TEXT:
            report["skipped"].append(
                {"program": program, "url": url, "reason": f"thin/JS-rendered ({total_text} chars)"}
            )
            continue

        snippets = _relevant_snippets(chunks)
        if not snippets:
            report["skipped"].append(
                {"program": program, "url": url, "reason": "no curriculum/outcome text found"}
            )
            continue

        cache[program] = {
            "url": url,
            "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "page_text_chars": total_text,
            "snippets": snippets,
        }
        report["succeeded"].append(
            {"program": program, "url": url, "page_chars": total_text, "snippets": len(snippets)}
        )

    with open(_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)

    return report


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

# Returned when nothing verified matches — downstream must phrase this as
# "the team can confirm on the call", NEVER invent an answer.
NOT_VERIFIED = {
    "verified": False,
    "note": "Not verified — the team can confirm the exact detail on the follow-up call.",
    "matches": [],
}

# Words too generic to be useful match keys.
_STOPWORDS = {
    "the", "and", "for", "with", "you", "your", "our", "that", "this", "are",
    "from", "what", "how", "why", "when", "does", "can", "will", "about", "into",
    "any", "all", "not", "but", "get", "got",
}

# Expand a query concept to related terms so keyword recall isn't brittle
# (e.g. a question about "financing" should also surface EMI / scholarship copy).
_QUERY_SYNONYMS = {
    "financing": {"emi", "scholarship", "upfront", "installment", "fee", "cost"},
    "finance": {"emi", "scholarship", "upfront", "fee", "cost"},
    "fees": {"fee", "cost", "emi", "price", "upfront", "scholarship"},
    "fee": {"cost", "emi", "price", "upfront", "scholarship"},
    "price": {"fee", "cost", "emi", "upfront"},
    "cost": {"fee", "emi", "upfront", "price"},
    "placement": {"placement", "job", "hiring", "career", "resume", "interview"},
    "salary": {"salary", "ctc", "package", "lpa", "hike"},
    "outcomes": {"salary", "placement", "hike", "career", "job"},
    "duration": {"months", "month", "weeks", "week", "year"},
}


def _words(text: str) -> set:
    """Lowercase word set (word-boundary tokens), so 'ai' won't match 'chain'."""
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _flatten_facts(facts, prefix=""):
    """Yield (path, value) leaves from verified_facts.json, skipping TODO_SCRAPE."""
    if isinstance(facts, dict):
        for k, v in facts.items():
            yield from _flatten_facts(v, f"{prefix}.{k}" if prefix else k)
    elif isinstance(facts, list):
        for i, v in enumerate(facts):
            yield from _flatten_facts(v, f"{prefix}[{i}]")
    else:
        yield prefix, facts


def retrieve(topic: str) -> dict:
    """Return only matched verified/cached snippets for `topic`.

    Word-boundary keyword match (with light synonym expansion) against
    verified_facts.json (source of truth) first, then the scraped cache.
    Returns NOT_VERIFIED if nothing solid matches — never invents.
    """
    query = {w for w in _words(topic or "") if len(w) > 2 and w not in _STOPWORDS}
    for w in list(query):
        query |= _QUERY_SYNONYMS.get(w, set())
    if not query:
        return NOT_VERIFIED

    matches = []

    # 1) Verified facts (skip unresolved TODO_SCRAPE placeholders).
    for path, value in _flatten_facts(load_facts()):
        sval = str(value)
        if "TODO_SCRAPE" in sval:
            continue
        if query & _words(f"{path} {sval}"):
            matches.append({"source": "verified_facts", "path": path, "text": sval})

    # 2) Scraped cache — a snippet matches only if it shares a real query word.
    for program, entry in _load_cache().items():
        for snip in entry.get("snippets", []):
            if query & _words(snip):
                matches.append({"source": "scraped", "program": program,
                                "url": entry.get("url"), "text": snip})

    if not matches:
        return NOT_VERIFIED

    # De-dupe on text, cap so we don't flood the answer prompt.
    seen, deduped = set(), []
    for m in matches:
        if m["text"] not in seen:
            seen.add(m["text"])
            deduped.append(m)
    return {"verified": True, "note": "", "matches": deduped[:12]}
