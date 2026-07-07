# Scaler AI Builder

**Two AI features for a phone-sales funnel, delivered over WhatsApp.**

Sales teams live on the phone. Two moments decide whether a lead converts: the *30 seconds
before* a call (does the rep sound like they know this person?) and the *follow-up after*
(does the lead get something that actually speaks to their doubts, or generic marketing?).
This project automates both — without ever letting an AI message a customer on its own.

1. **Pre-call nudge → the sales rep.** A short, scannable prep brief pushed to the rep's
   WhatsApp right before they dial, so the opening doesn't sound canned.
2. **Post-call personalised PDF → the lead.** A 2–3 page follow-up tailored to *that lead's*
   goals and objections, sent only after the rep taps **Approve** — nothing customer-facing
   fires automatically.

Everything runs on free tiers and deploys to a single always-on Streamlit app.

---

## How it works

```
Lead profile + call transcript (or audio recording)
        │
        ├─►  transcribe (if audio)  ──►  Groq Whisper
        │
        ├─►  pre-call nudge   ──►  Gemini 2.5 Flash  ──►  WhatsApp to the rep
        │
        └─►  personalised PDF ──►  Gemini → grounded content
                                   → WeasyPrint (HTML+CSS → PDF)
                                   → Cloudinary (public link)
                                   → [ Approve / Edit / Skip gate ]
                                   → WhatsApp to the lead
```

Two design rules the whole thing is built around:

- **Never fabricate facts.** All product-specific claims come from a verified facts file;
  if something isn't verified, the copy says "we'll confirm on the next call" instead of
  inventing it.
- **Personalisation is the point.** The follow-up for a ROI-driven lead should look and read
  visibly different from one for a security-conscious lead — different content *and* different
  visual accent.

---

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

---

## Project status

This is being built in stages. **Step 1 is done and deployable:** a working Streamlit app that
proves the two riskiest end-to-end paths with *real* API calls (no mocks):

- ✅ Streamlit → Twilio → WhatsApp **text** lands on a real phone.
- ✅ Streamlit → WeasyPrint **PDF** → Cloudinary → Twilio → WhatsApp **document** lands on a real phone.

Roadmap (in order): grounding & verified facts → pre-call nudge → personalised PDF generator →
audio transcription → approval gate & onboarding UI. `nudge.py`, `pdf_gen.py`, `stt.py`, and
`grounding.py` are currently stubs with TODOs marking where each stage plugs in.

---

## Repository layout

```
app.py               Streamlit UI (currently the step-1 smoke test)
whatsapp.py          Cloudinary upload + Twilio WhatsApp send
llm.py               Gemini call with Groq fallback
prompts.py           All prompt strings, in one place
grounding.py         Verified-facts loader + scraper   (stub)
nudge.py             Pre-call nudge generator          (stub)
pdf_gen.py           Personalised PDF pipeline         (stub)
stt.py               Audio transcription               (stub)
verified_facts.json  The only source of product claims
requirements.txt     Python deps
packages.txt         System libs WeasyPrint needs on Linux
```

---

## Run it locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create `.streamlit/secrets.toml` (copy `.streamlit/secrets.toml.example` and fill in real
keys — this file is gitignored and must never be committed), then:

```powershell
streamlit run app.py
```

> **Note on WeasyPrint + Windows:** WeasyPrint needs GTK/Pango/Cairo native libraries. On
> Linux (and Streamlit Cloud) these are installed automatically via `packages.txt`. On Windows
> the PDF button needs the GTK runtime installed separately — but the text button works either
> way, and the full PDF path works on the deployed app.

Before sending, message the Twilio WhatsApp sandbox from your test phone (send its join code)
so you're inside the 24-hour messaging window.

## Deploy (Streamlit Community Cloud)

1. Push to GitHub — `.gitignore` keeps `secrets.toml` out of the repo.
2. On [share.streamlit.io](https://share.streamlit.io), create an app pointing at this repo,
   branch `main`, main file `app.py`.
3. In the app's **Settings → Secrets**, paste the same keys as your local `secrets.toml`.
4. `requirements.txt` and `packages.txt` are picked up automatically; the first build installs
   the WeasyPrint system libraries.

---

## Security

No credentials are committed. `.streamlit/secrets.toml` is gitignored, and all keys are read at
runtime from Streamlit secrets. If you fork this, use your own API keys.
