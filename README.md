# Scaler AI Builder

## What you built

Two AI features for Scaler's phone-sales funnel, both delivered on WhatsApp. Before a
call, the app generates a short, scannable pre-call nudge — who this lead is, their
likely persona, angles that'll land, objections to expect, an opening hook, all tagged
`[fact]`/`[inferred]`/`[missing]` — and sends it straight to the BDA's WhatsApp, no
approval needed since it's internal. After a call (from a pasted transcript or an
uploaded audio recording), it extracts the lead's genuine open questions, answers them
using only grounded Scaler facts (scraped from scaler.com plus a verified-facts file,
never fabricated), and renders a personalised 2–3 page PDF whose colour, headline, and
emphasis shift with the lead's own goal and tone — Rohan's ROI-driven brief reads and
looks nothing like Meera's reassurance-driven one. That PDF is lead-facing, so it's
routed through the BDA for **Approve / Edit / Skip**; nothing reaches the lead without
an explicit Approve.

## One failure

The model paraphrased a grounded stat — scraped from scaler.com as "wage premium
doubled FROM 25%" — into "doubled TO 25%" in Rohan's follow-up PDF. The number was
grounded, but its meaning was inverted. Fix: quote grounded numbers verbatim or omit
them; the PDF evidence block now drops external market/salary stats entirely.

## Scale plan

At 100k leads/month (~3,300/day) two things break first. **WhatsApp throughput**: the
Twilio sandbox is single-number and rate-limited, and most sends would fall outside the
24-hour free-form window — production needs a paid WhatsApp Business number with
approved template messages. **The approval gate**: every lead-facing PDF needs a human
Approve, which doesn't scale past a few hundred BDAs. The fix isn't removing the gate —
it's making it selective, auto-clearing low-risk PDFs (no unanswered pricing/outcome
questions, high grounding confidence) and routing only ambiguous ones to a human.

---

## How it works

```
Lead profile + call transcript (or audio recording)
        │
        ├─►  transcribe (if audio)  ──►  Groq Whisper
        │
        ├─►  pre-call nudge   ──►  Gemini 2.5 Flash  ──►  WhatsApp to the BDA (no gate)
        │
        └─►  personalised PDF ──►  Gemini → grounded content
                                   → WeasyPrint (HTML+CSS → PDF)
                                   → Cloudinary (public link)
                                   → [ Approve / Edit / Skip gate ]
                                   → WhatsApp to the lead
```

Two design rules the whole thing is built around:

- **Never fabricate facts.** All product-specific claims come from a verified facts
  file plus a scaler.com scrape; if something isn't grounded, the copy says "we'll
  confirm on the next call" instead of inventing it.
- **Personalisation is the point.** The follow-up for a ROI-driven lead reads and
  looks visibly different from one for a security-conscious lead — different content
  *and* a different visual accent, both derived from that lead's own goal and tone.

## Tech stack

| Layer | Choice |
|---|---|
| App + UI | Python + [Streamlit](https://streamlit.io) (free, always-on hosting) |
| LLM (primary) | Google **Gemini 2.5 Flash** |
| LLM (fallback) | **Groq** `llama-3.3-70b-versatile` |
| Speech-to-text | Groq **Whisper** `whisper-large-v3-turbo` |
| PDF | **WeasyPrint** (HTML + CSS → PDF) |
| PDF hosting | **Cloudinary** (public link for the attachment) |
| WhatsApp delivery | **Twilio** WhatsApp API |
| Grounding | `requests` + BeautifulSoup + a verified-facts file |

## Repository layout

```
app.py               Streamlit UI: onboarding, pre-call nudge, post-call PDF + gate
whatsapp.py          Cloudinary upload + Twilio WhatsApp send
llm.py               Gemini call with Groq fallback
prompts.py           Base prompt strings (guardrails appended at call time in nudge.py/pdf_gen.py)
grounding.py         Verified-facts loader + scaler.com scraper + retrieve(topic)
nudge.py             Pre-call nudge generator
pdf_gen.py           extract_questions -> answer_questions -> render_pdf pipeline
stt.py               Audio transcription (Groq Whisper)
verified_facts.json  The only source of product claims (plus scraped_cache.json)
requirements.txt     Python deps
packages.txt         System libs WeasyPrint needs on Linux
```

## Run it locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create `.streamlit/secrets.toml` (gitignored — never commit it) with your own keys:

```toml
GEMINI_API_KEY = "..."
GROQ_API_KEY = "..."
TWILIO_ACCOUNT_SID = "..."
TWILIO_AUTH_TOKEN = "..."
TWILIO_WHATSAPP_FROM = "whatsapp:+14155238886"
CLOUDINARY_URL = "cloudinary://<api_key>:<api_secret>@<cloud_name>"
MY_TEST_WHATSAPP = "whatsapp:+91XXXXXXXXXX"
```

Then run:

```powershell
streamlit run app.py
```

> **Note on WeasyPrint + Windows:** WeasyPrint needs GTK/Pango/Cairo native libraries. On
> Linux (and Streamlit Cloud) these are installed automatically via `packages.txt`. On
> Windows the PDF render step needs the GTK runtime installed separately — the app falls
> back to an HTML preview locally and renders the real PDF on the deployed app.

Before sending, message the Twilio WhatsApp sandbox from your test phone (send its join
code) so you're inside the 24-hour messaging window.

## Deploy (Streamlit Community Cloud)

1. Push to GitHub — `.gitignore` keeps `secrets.toml` out of the repo.
2. On [share.streamlit.io](https://share.streamlit.io), create an app pointing at this
   repo, branch `main`, main file `app.py`.
3. In the app's **Settings → Secrets**, paste the same keys as your local `secrets.toml`.
4. `requirements.txt` and `packages.txt` are picked up automatically; the first build
   installs the WeasyPrint system libraries.

> **Cloudinary gotcha:** new Cloudinary accounts block delivery of `.pdf` URLs by
> default. Enable **Settings → Security → "Allow delivery of PDF and ZIP files"**, or
> WhatsApp can't fetch the attachment (the URL returns 401 and Twilio reports error 63019).

## Security

No credentials are committed. `.streamlit/secrets.toml` is gitignored, and all keys are
read at runtime from Streamlit secrets. If you fork this, use your own API keys.
