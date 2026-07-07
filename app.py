"""Scaler AI Builder — Streamlit app.

Step 1: smoke test (WhatsApp text + PDF end to end).
Step 2: grounding (verified facts + scraped scaler.com cache).
Step 3: pre-call nudge (BDA-facing, no approval gate).
Step 4: post-call personalised PDF + approval gate (structured input).
Step 5: audio input path (transcribe -> same PDF pipeline).
"""

import base64

import streamlit as st
import streamlit.components.v1 as components

import grounding
import nudge as nudge_mod
import pdf_gen
import stt
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
# Post-call personalised PDF (SPEC §6b/§6c/§7) — LEAD-FACING, approval gated
# ===========================================================================
st.divider()
st.header("Post-call personalised PDF")
st.caption("Lead-facing. Nothing sends without **Approve**.")


def _clear_pdf_state():
    for k in ("pdf_qdata", "pdf_content", "pdf_bytes", "pdf_cover",
              "pdf_render_error", "pdf_editing"):
        st.session_state.pop(k, None)


def _render_into_state(content):
    try:
        st.session_state["pdf_bytes"] = pdf_gen.render_pdf(content)
        st.session_state.pop("pdf_render_error", None)
    except Exception as e:  # noqa: BLE001 — WeasyPrint may lack GTK locally
        st.session_state["pdf_bytes"] = None
        st.session_state["pdf_render_error"] = str(e)


lead_profile = st.text_area("Lead profile", height=140, key="pdf_profile",
                            placeholder="Paste the lead's profile…")

mode = st.radio("Input mode", ["Structured (transcript)", "Audio (recording)"],
                horizontal=True, key="pdf_mode")

if mode.startswith("Structured"):
    transcript = st.text_area("Call transcript", height=180, key="pdf_transcript",
                              placeholder="Paste the call transcript…")
else:
    audio = st.file_uploader("Call recording", type=["mp3", "m4a", "wav"], key="pdf_audio")
    if st.button("Transcribe audio"):
        if audio is None:
            st.warning("Upload an audio file first.")
        else:
            with st.spinner("Transcribing with Groq Whisper…"):
                try:
                    # Only produces text; it then feeds the SAME pipeline below.
                    st.session_state["pdf_audio_tx_review"] = stt.transcribe(
                        audio.getvalue(), audio.name)
                except Exception as e:  # noqa: BLE001
                    st.error(str(e))
    # Show the transcript to the BDA before generating (editable so they can fix it).
    transcript = st.text_area(
        "Transcript (from audio — review/edit before generating)",
        height=180, key="pdf_audio_tx_review",
    )

lead_to = st.text_input("Lead's WhatsApp number", value=TO, key="pdf_lead_to")

if st.button("Generate PDF", type="primary"):
    if not lead_profile.strip() or not (transcript or "").strip():
        st.warning("Need a lead profile and a transcript (paste one, or transcribe an audio file).")
    else:
        _clear_pdf_state()
        with st.spinner("Extracting questions → grounding answers → rendering…"):
            try:
                qdata, content = pdf_gen.generate_pdf_content(lead_profile, transcript)
                st.session_state["pdf_qdata"] = qdata
                st.session_state["pdf_content"] = content
                st.session_state["pdf_cover"] = pdf_gen.draft_covering_message(qdata, content)
                _render_into_state(content)
            except Exception as e:  # noqa: BLE001
                st.error(f"PDF generation failed: {e}")

if st.session_state.get("pdf_content"):
    qdata = st.session_state["pdf_qdata"]
    content = st.session_state["pdf_content"]

    with st.expander("Extracted questions / goal / tone / theme", expanded=True):
        st.write("**Lead goal:**", qdata.get("lead_goal", ""))
        st.write("**Tone read:**", qdata.get("tone_read", ""))
        st.write("**Accent theme:**", f"`{content.get('accent_theme', '')}`")
        st.write("**Open questions:**")
        for q in qdata.get("questions", []):
            st.write(f"- {q}")

    st.subheader("Preview")
    if st.session_state.get("pdf_bytes"):
        b64 = base64.b64encode(st.session_state["pdf_bytes"]).decode()
        st.markdown(
            f'<iframe src="data:application/pdf;base64,{b64}" width="100%" '
            'height="520" style="border:1px solid #ddd;border-radius:8px;"></iframe>',
            unsafe_allow_html=True,
        )
        st.download_button("Download PDF", data=st.session_state["pdf_bytes"],
                           file_name="scaler_followup.pdf", mime="application/pdf")
    else:
        st.warning(
            "PDF render unavailable here (WeasyPrint needs GTK — works on Streamlit "
            f"Cloud). Showing HTML preview instead. [{st.session_state.get('pdf_render_error','')[:80]}]"
        )
        components.html(pdf_gen._build_html(content), height=560, scrolling=True)

    st.write("**Covering WhatsApp message (draft):**")
    st.info(st.session_state.get("pdf_cover", ""))

    # ---- Approval gate ----
    st.subheader("Approval gate")
    c1, c2, c3 = st.columns(3)
    approve = c1.button("✅ Approve & send", use_container_width=True)
    edit = c2.button("✏️ Edit", use_container_width=True)
    skip = c3.button("🚫 Skip", use_container_width=True)

    if edit:
        st.session_state["pdf_editing"] = True
    if skip:
        _clear_pdf_state()
        st.info("Discarded — nothing sent.")
        st.stop()

    if st.session_state.get("pdf_editing"):
        with st.form("edit_pdf"):
            new_cover = st.text_area("Covering message", value=st.session_state["pdf_cover"])
            new_headline = st.text_input("Headline", value=content.get("headline", ""))
            new_opening = st.text_area("Opening", value=content.get("opening", ""))
            new_whynow = st.text_area("Why now", value=content.get("why_now", ""))
            new_closing = st.text_area("Closing", value=content.get("closing", ""))
            if st.form_submit_button("Save & re-render"):
                content.update(headline=new_headline, opening=new_opening,
                               why_now=new_whynow, closing=new_closing)
                st.session_state["pdf_content"] = content
                st.session_state["pdf_cover"] = new_cover
                _render_into_state(content)
                st.session_state["pdf_editing"] = False
                st.rerun()

    if approve:
        if not st.session_state.get("pdf_bytes"):
            st.error("No rendered PDF to send (render failed here — try on the deployed app).")
        else:
            try:
                url = upload_to_cloudinary(st.session_state["pdf_bytes"])
                sid_pdf = send_whatsapp_pdf(lead_to, url,
                                            caption=content.get("headline", "Your Scaler follow-up"))
                sid_txt = send_whatsapp_text(lead_to, st.session_state["pdf_cover"])
                st.success("Sent to the lead.")
                st.code(f"Cloudinary: {url}")
                st.code(f"PDF SID: {sid_pdf}")
                st.code(f"Message SID: {sid_txt}")
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
