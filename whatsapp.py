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
from urllib.parse import urlparse

import requests
import streamlit as st
import cloudinary
import cloudinary.uploader


# ---------------------------------------------------------------------------
# Cloudinary (PDF hosting -> public https URL that Twilio can fetch)
# ---------------------------------------------------------------------------

def _configure_cloudinary():
    # CLOUDINARY_URL format: cloudinary://<api_key>:<api_secret>@<cloud_name>
    # NOTE: cloudinary.config(cloudinary_url=...) does NOT parse the URL (it only
    # stores it), so we parse it ourselves and pass the fields explicitly.
    parsed = urlparse(st.secrets["CLOUDINARY_URL"].strip())
    cloudinary.config(
        cloud_name=parsed.hostname,
        api_key=parsed.username,
        api_secret=parsed.password,
        secure=True,
    )


def upload_to_cloudinary(pdf_bytes, public_id=None):
    """Upload raw PDF bytes to Cloudinary and return a public secure_url that
    ends in `.pdf` and serves as application/pdf.

    Twilio raises error 63019 ("Media failed to download") when the media URL
    has no `.pdf` extension / proper content-type. The reliable fix with
    resource_type="raw" is to bake the `.pdf` extension directly into the
    public_id, so the delivered secure_url ends in `.pdf`. If for some reason
    that doesn't yield a `.pdf` URL, we fall back to resource_type="auto"
    (Cloudinary's PDF/image pipeline), which returns a `.pdf` secure_url too.
    """
    _configure_cloudinary()
    if public_id is None:
        public_id = f"scaler_pdf_{uuid.uuid4().hex[:12]}"

    def _upload(resource_type, pid):
        result = cloudinary.uploader.upload(
            io.BytesIO(pdf_bytes),
            resource_type=resource_type,
            public_id=pid,
            overwrite=True,
        )
        return result["secure_url"]

    # Primary: raw upload with the extension in the public_id -> URL ends in .pdf.
    url = _upload("raw", f"{public_id}.pdf")
    if not url.lower().endswith(".pdf"):
        # Fallback: let Cloudinary auto-detect the PDF; its secure_url ends .pdf.
        url = _upload("auto", public_id)

    print(f"[cloudinary] upload secure_url: {url}")
    return url


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
