"""
email_sender.py — Gmail email sending utility
Separated from main.py to avoid circular imports with email_digest.py

Two ways to send, tried in this order:

1. Gmail SMTP with an App Password (GMAIL_APP_PASSWORD) — preferred. An app
   password never expires. The OAuth path below broke silently on
   2026-10-16 ("invalid_grant": the Google Cloud app is in "Testing"
   status, where Google expires refresh tokens after 7 days, and the
   "Publish app" button was unavailable for this project).
2. Gmail API with the stored OAuth2 token (token.json) — the original
   path, kept as a fallback so email keeps working until the
   GMAIL_APP_PASSWORD secret is set.
"""

import logging
import base64
import mimetypes
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path

from config import GMAIL_APP_PASSWORD, GMAIL_SENDER

logger = logging.getLogger(__name__)

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465


def _build_message(subject, html_body, notify_email, attachments):
    msg = MIMEMultipart("mixed" if attachments else "alternative")
    msg["Subject"] = subject
    msg["To"] = notify_email
    msg.attach(MIMEText(html_body, "html"))

    for path in attachments or []:
        p = Path(path)
        if not p.exists():
            logger.warning(f"Attachment not found, skipping: {p}")
            continue
        ctype, _ = mimetypes.guess_type(str(p))
        maintype, subtype = (ctype or "application/octet-stream").split("/", 1)
        part = MIMEBase(maintype, subtype)
        part.set_payload(p.read_bytes())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", "attachment", filename=p.name)
        msg.attach(part)
    return msg


def _send_via_smtp(msg, notify_email) -> bool:
    if not GMAIL_SENDER:
        logger.error("GMAIL_APP_PASSWORD is set but no sender address (GMAIL_SENDER/JOB_EMAIL) — cannot send via SMTP")
        return False
    try:
        # Google displays app passwords in groups of four ("abcd efgh ...");
        # the spaces aren't part of the password.
        password = GMAIL_APP_PASSWORD.replace(" ", "")
        # Only set on this path — the Gmail API path fills From in itself
        # from the authorized account.
        if "From" not in msg:
            msg["From"] = GMAIL_SENDER
        # smtplib's default TLS context does NOT verify the server
        # certificate — pass a verifying one so the password can only ever
        # be sent to the real smtp.gmail.com.
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=60, context=ssl.create_default_context()) as smtp:
            smtp.login(GMAIL_SENDER, password)
            smtp.send_message(msg, from_addr=GMAIL_SENDER, to_addrs=[notify_email])
        logger.info(f"Email report sent to {notify_email} (SMTP, app password)")
        return True
    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"Gmail rejected the app password for {GMAIL_SENDER}: {e}")
        return False
    except Exception as e:
        logger.exception(f"SMTP email send failed: {e}")
        return False


def send_email_report(
    subject: str,
    html_body: str,
    notify_email: str,
    credentials_file: str,
    token_file: str,
    scopes: list,
    attachments: list[str] | None = None,
) -> bool:
    """Send HTML email — Gmail SMTP with an app password when configured,
    otherwise the Gmail API with the stored OAuth2 token."""
    logger.info(f"Inside send_email_report for subject: {subject}")
    msg = _build_message(subject, html_body, notify_email, attachments)

    if GMAIL_APP_PASSWORD:
        if _send_via_smtp(msg, notify_email):
            return True
        logger.warning("SMTP send failed — falling back to the Gmail API OAuth token")
        del msg["From"]  # let the Gmail API set From from the authorized account

    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        logger.info("Checking credentials...")
        creds = None
        if Path(token_file).exists():
            creds = Credentials.from_authorized_user_file(str(token_file), scopes)

        logger.info(f"Creds valid: {creds.valid if creds else 'None'}")

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                logger.info("Refreshing creds...")
                creds.refresh(Request())
            else:
                if not Path(credentials_file).exists():
                    logger.error("credentials.json not found — cannot send email")
                    return False
                logger.info("Running local server for auth...")
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(credentials_file), scopes
                )
                creds = flow.run_local_server(port=0)
            Path(token_file).write_text(creds.to_json())

        logger.info("Building gmail service...")
        service = build("gmail", "v1", credentials=creds)

        logger.info("Sending message...")
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        service.users().messages().send(userId="me", body={"raw": raw}).execute()
        logger.info(f"Email report sent to {notify_email}")
        return True

    except ImportError:
        logger.error("google-api-python-client not installed.")
        return False
    except Exception as e:
        logger.exception(f"Email send failed: {e}")
        return False
