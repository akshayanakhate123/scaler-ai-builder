"""Scaler AI Builder — Streamlit app.

Step 1: smoke test (WhatsApp text + PDF end to end).
Step 2: grounding (verified facts + scraped scaler.com cache).
Step 3: pre-call nudge (BDA-facing, no approval gate).
"""

import streamlit as st

import grounding
import nudge as nudge_mod
from whatsapp import upload_to_cloudinary, send_whatsapp_text, send_whatsapp_pdf

st.set_page_config(page_title="Scaler AI Builder", page_icon="📞")


# ---------------------------------------------------------------------------
# Grounding on deploy (Task A): try a live scrape refresh once per hour; on any
# failure keep the committed snapshot. scrape_scaler merge-starts from that
# snapshot, so retrieve() always has grounding whether or not the refresh works.
# ---------------------------------------------------------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def refresh_grounding():
    try:
        return grounding.scrape_scaler(timeout=12)
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


refresh_grounding()

TO = st.secrets.get("MY_TEST_WHATSAPP", "")

st.title("Scaler AI Builder")

if not TO:
    st.error(
        "MY_TEST_WHATSAPP is not set in secrets. Add it to .streamlit/secrets.toml "
        '(e.g. MY_TEST_WHATSAPP = "whatsapp:+91XXXXXXXXXX").'
    )
    st.stop()

st.caption(
    f"Test recipient: **{TO}**. Twilio sandbox note: this number must have messaged "
    "the sandbox in the last 24h or sends will fail."
)


# ===========================================================================
# Pre-call nudge (SPEC §6a) — BDA-facing, NO approval gate
# ===========================================================================
st.header("Pre-call nudge")
st.caption("Internal prep for the BDA. Sends straight to the BDA — no approval gate.")

profile = st.text_area(
    "Lead profile",
    height=200,
    placeholder="Paste the lead's profile / notes here…",
    key="nudge_profile",
)

if st.button("Generate nudge", type="primary"):
    if not profile.strip():
        st.warning("Paste a lead profile first.")
    else:
        with st.spinner("Generating grounded nudge…"):
            try:
                st.session_state["nudge_text"] = nudge_mod.generate_nudge(profile)
            except Exception as e:  # noqa: BLE001
                st.session_state.pop("nudge_text", None)
                st.error(f"Nudge generation failed: {e}")

if st.session_state.get("nudge_text"):
    st.markdown(st.session_state["nudge_text"])
    if st.button("Send to BDA WhatsApp"):
        try:
            sid = send_whatsapp_text(TO, st.session_state["nudge_text"])
            st.success("Sent to BDA.")
            st.code(sid)
        except Exception as e:  # noqa: BLE001
            st.error(f"Send failed: {e}")


# ===========================================================================
# Step-1 smoke test (kept for regression checks)
# ===========================================================================
with st.expander("Smoke test: WhatsApp text + PDF (step 1)"):
    col1, col2 = st.columns(2)

    with col1:
        if st.button("Send test text", use_container_width=True):
            try:
                sid = send_whatsapp_text(
                    TO,
                    "✅ Scaler AI Builder — text test. Streamlit → Twilio → WhatsApp works.",
                )
                st.success("Text sent.")
                st.code(sid)
            except Exception as e:  # noqa: BLE001
                st.error(f"Text send failed: {e}")

    with col2:
        if st.button("Send test PDF", use_container_width=True):
            try:
                from weasyprint import HTML

                html = """
                <html><head><meta charset="utf-8"></head>
                <body style="font-family: sans-serif; padding: 40px;">
                  <h1 style="color:#2440d1;">Scaler AI Builder</h1>
                  <p>Test PDF — WeasyPrint → Cloudinary → WhatsApp via Twilio.</p>
                </body></html>
                """
                pdf_bytes = HTML(string=html).write_pdf()
                st.success("PDF generated.")
                url = upload_to_cloudinary(pdf_bytes)
                st.code(url)
                sid = send_whatsapp_pdf(TO, url, caption="Scaler AI Builder — test PDF ✅")
                st.success("PDF sent.")
                st.code(sid)
                st.download_button(
                    "Download the PDF locally",
                    data=pdf_bytes,
                    file_name="scaler_test.pdf",
                    mime="application/pdf",
                )
            except Exception as e:  # noqa: BLE001
                st.error(f"PDF path failed: {e}")
