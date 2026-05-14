import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from db import get_settings

_logger = logging.getLogger(__name__)


def send_email(to_email: str, display_name: str, subject: str, html: str) -> bool:
    s = get_settings()
    if not s.smtp_user:
        _logger.debug("SMTP not configured — skipping email to %s", to_email)
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = s.smtp_from or s.smtp_user
        msg["To"] = to_email
        msg.attach(MIMEText(html, "html", "utf-8"))

        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.login(s.smtp_user, s.smtp_password)
            server.sendmail(msg["From"], [to_email], msg.as_string())
        _logger.info("Email sent to %s: %s", to_email, subject)
        return True
    except Exception as exc:
        _logger.error("Failed to send email to %s: %s", to_email, exc)
        return False
