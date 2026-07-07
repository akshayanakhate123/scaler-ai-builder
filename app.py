"""Scaler AI Builder — Step 1 skeleton.

Purpose of this page: prove the two riskiest end-to-end paths with REAL API calls
(no mocks):
    1. Streamlit -> Twilio -> WhatsApp text lands on a real phone.
    2. Streamlit -> WeasyPrint PDF -> Cloudinary -> Twilio -> WhatsApp document.

Everything else in SPEC.md (nudge, PDF content generation, STT, grounding,
approval gate) is intentionally NOT built yet — see the stub modules.
"""

import streamlit as st

from whatsapp import upload_to_cloudinary, send_whatsapp_text, send_whatsapp_pdf

st.set_page_config(page_title="Scaler AI Builder — Step 1", page_icon="📞")

st.title("Scaler AI Builder — Step 1 smoke test")
st.caption(
    "Proves deploy + WhatsApp text + WhatsApp PDF end to end with real API calls."
)

# Destination is fixed to the test number in secrets for this smoke test.
TO = st.secrets.get("MY_TEST_WHATSAPP", "")

if not TO:
    st.error(
        "MY_TEST_WHATSAPP is not set in secrets. Add it to .streamlit/secrets.toml "
        '(e.g. MY_TEST_WHATSAPP = "whatsapp:+91XXXXXXXXXX").'
    )
    st.stop()

st.info(
    f"Sending to **{TO}**. Reminder: with the Twilio sandbox this number must have "
    "sent the join code to the sandbox number within the last 24h, or sends will fail."
)

col1, col2 = st.columns(2)

# ---------------------------------------------------------------------------
# Test 1 — WhatsApp text
# ---------------------------------------------------------------------------
with col1:
    st.subheader("1. Send test text")
    if st.button("Send test text", use_container_width=True):
        try:
            sid = send_whatsapp_text(
                TO,
                "✅ Scaler AI Builder — Step 1 text test. If you see this, the "
                "Streamlit → Twilio → WhatsApp path works.",
            )
            st.success("Text sent.")
            st.write("**Twilio message SID:**")
            st.code(sid)
        except Exception as e:  # noqa: BLE001 — surface any failure to the demo UI
            st.error(f"Text send failed: {e}")

# ---------------------------------------------------------------------------
# Test 2 — WhatsApp PDF (WeasyPrint -> Cloudinary -> Twilio)
# ---------------------------------------------------------------------------
with col2:
    st.subheader("2. Send test PDF")
    if st.button("Send test PDF", use_container_width=True):
        try:
            # Import here so the text path still works even if WeasyPrint's
            # native deps aren't present locally (they are on Streamlit Cloud
            # via packages.txt).
            from weasyprint import HTML

            html = """
            <html>
              <head><meta charset="utf-8"></head>
              <body style="font-family: sans-serif; padding: 40px;">
                <h1 style="color:#2440d1;">Scaler AI Builder</h1>
                <p>Step 1 test PDF — generated with WeasyPrint, hosted on
                   Cloudinary, delivered over WhatsApp via Twilio.</p>
              </body>
            </html>
            """
            pdf_bytes = HTML(string=html).write_pdf()
            st.success("PDF generated with WeasyPrint.")

            url = upload_to_cloudinary(pdf_bytes)
            st.write("**Cloudinary URL:**")
            st.code(url)

            sid = send_whatsapp_pdf(
                TO,
                url,
                caption="Scaler AI Builder — Step 1 test PDF ✅",
            )
            st.success("PDF sent.")
            st.write("**Twilio message SID:**")
            st.code(sid)

            # Always offer a local download so a demo never dead-ends.
            st.download_button(
                "Download the PDF locally",
                data=pdf_bytes,
                file_name="scaler_step1_test.pdf",
                mime="application/pdf",
            )
        except Exception as e:  # noqa: BLE001
            st.error(f"PDF path failed: {e}")
