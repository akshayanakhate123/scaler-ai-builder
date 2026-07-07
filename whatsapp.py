"""WhatsApp + PDF hosting helpers.

NOTE ON PROVIDER: SPEC.md section 8 describes the Meta WhatsApp Cloud API, but
the credentials provided for this build are Twilio's WhatsApp sandbox
(TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / TWILIO_WHATSAPP_FROM). This module is
therefore implemented against Twilio. Twilio's REST API is a plain HTTP POST, so
we call it with `requests` and do NOT need the `twilio` SDK — requirements.txt
stays exactly as SPEC.md lists it.

Function signatures match the build brief:
    upload_to_cloudinary(pdf_bytes) -> secure_url
    send_whatsapp_text(to, body)   -> message SID
    send_whatsapp_pdf(to, media_url, caption) -> message SID

All credentials are read from st.secrets.
"""

import io
import uuid

import requests
import streamlit as st
import cloudinary
import cloudinary.uploader


# ---------------------------------------------------------------------------
# Cloudinary (PDF hosting -> public https URL that Twilio can fetch)
# ---------------------------------------------------------------------------

def _configure_cloudinary():
    # CLOUDINARY_URL format: cloudinary://<api_key>:<api_secret>@<cloud_name>
    cloudinary.config(cloudinary_url=st.secrets["CLOUDINARY_URL"].strip())


def upload_to_cloudinary(pdf_bytes, public_id=None):
    """Upload raw PDF bytes to Cloudinary and return a public secure_url.

    Uses resource_type="raw" so Cloudinary serves the file untouched with a
    `.pdf` extension, which is what Twilio/WhatsApp need to treat it as a
    document attachment.
    """
    _configure_cloudinary()
    if public_id is None:
        public_id = f"scaler/test_{uuid.uuid4().hex[:12]}"
    result = cloudinary.uploader.upload(
        io.BytesIO(pdf_bytes),
        resource_type="raw",
        public_id=public_id,
        format="pdf",
        overwrite=True,
    )
    return result["secure_url"]


# ---------------------------------------------------------------------------
# Twilio WhatsApp (plain REST, no SDK)
# ---------------------------------------------------------------------------

def _twilio_creds():
    sid = st.secrets["TWILIO_ACCOUNT_SID"]
    token = st.secrets["TWILIO_AUTH_TOKEN"]
    from_ = st.secrets["TWILIO_WHATSAPP_FROM"]  # e.g. "whatsapp:+14155238886"
    return sid, token, from_


def _messages_url(sid):
    return f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"


def send_whatsapp_text(to, body):
    """Send a free-form WhatsApp text. Returns the Twilio message SID.

    `to` must be in the form "whatsapp:+91XXXXXXXXXX".
    """
    sid, token, from_ = _twilio_creds()
    resp = requests.post(
        _messages_url(sid),
        data={"From": from_, "To": to, "Body": body},
        auth=(sid, token),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["sid"]


def send_whatsapp_pdf(to, media_url, caption=""):
    """Send a PDF (hosted at `media_url`) as a WhatsApp media message.

    Returns the Twilio message SID. `caption` is sent as the message body.
    """
    sid, token, from_ = _twilio_creds()
    data = {"From": from_, "To": to, "MediaUrl": media_url}
    if caption:
        data["Body"] = caption
    resp = requests.post(
        _messages_url(sid),
        data=data,
        auth=(sid, token),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["sid"]
