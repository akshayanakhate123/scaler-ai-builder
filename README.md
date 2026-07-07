# Scaler AI Builder

AI features for Scaler's phone-sales funnel, delivered over WhatsApp. See `SPEC.md`
for the full plan. **This repo is currently at build-order step 1** — a deployable
Streamlit skeleton that proves the two riskiest end-to-end paths with real API calls:

1. Streamlit → Twilio → WhatsApp **text**.
2. Streamlit → WeasyPrint **PDF** → Cloudinary → Twilio → WhatsApp **document**.

`nudge.py`, `pdf_gen.py`, `stt.py`, `grounding.py` are intentionally stubs for now.

> Provider note: SPEC.md describes the Meta WhatsApp Cloud API, but this build uses
> **Twilio's WhatsApp sandbox** (that's what the provided credentials are for).
> `whatsapp.py` calls Twilio's REST API directly with `requests`, so no extra
> dependency is needed.

## Run locally

1. Create and activate a virtual environment, then install deps:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
   > WeasyPrint needs GTK/Pango/Cairo native libraries. On Linux these come from
   > `packages.txt`; on Windows you must install the GTK runtime for `import
   > weasyprint` to work. If it won't import locally, the text button still works,
   > and the PDF path works once deployed to Streamlit Cloud.

2. Create `.streamlit/secrets.toml` (copy from `.streamlit/secrets.toml.example`)
   and fill in real keys. This file is gitignored — never commit it.

3. Run:
   ```powershell
   streamlit run app.py
   ```

4. Before sending: from your test phone, send the Twilio sandbox **join code** to
   the sandbox number (`+1 415 523 8886`). Free-form WhatsApp sends only work inside
   the 24-hour window after the recipient last messaged the sandbox.

## Deploy to Streamlit Community Cloud

1. Push this repo to GitHub (the `.gitignore` keeps `secrets.toml` out).
2. On [share.streamlit.io](https://share.streamlit.io), create an app pointing at
   this repo, branch, and `app.py`.
3. In the app's **Settings → Secrets**, paste the same key/values as your local
   `secrets.toml`.
4. `requirements.txt` and `packages.txt` are picked up automatically — `packages.txt`
   installs the apt libraries WeasyPrint needs on Linux.
5. Deploy, then hit both buttons to confirm text + PDF land on WhatsApp.
