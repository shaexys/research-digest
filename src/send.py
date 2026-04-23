"""Gmail SMTP email delivery with retry."""

import os
import smtplib
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def send_email(html: str, subject: str, sender_name: str = "Research Digest") -> None:
    """Send HTML email via Gmail SMTP with retry on transient failures."""
    gmail_user = os.environ["GMAIL_USER"]
    gmail_app_password = os.environ["GMAIL_APP_PASSWORD"]
    to_email = os.environ["EMAIL_TO"]

    msg = MIMEMultipart("alternative")
    msg["From"] = f"{sender_name} <{gmail_user}>"
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(html, "html"))

    for attempt in range(3):
        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as server:
                server.login(gmail_user, gmail_app_password)
                server.sendmail(gmail_user, to_email, msg.as_string())
            print("Email sent via Gmail SMTP")
            return
        except (smtplib.SMTPException, OSError) as e:
            wait = 10 * (attempt + 1)
            print(f"    SMTP send failed ({e}), retrying in {wait}s (attempt {attempt + 1}/3)")
            time.sleep(wait)

    raise RuntimeError("Email send failed after 3 attempts")
