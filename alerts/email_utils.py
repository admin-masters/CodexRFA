import logging
from typing import List
from django.conf import settings
from django.template.loader import render_to_string
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

logger = logging.getLogger(__name__)


def send_redflag_email(doctor, submission, red_flags: List[dict]):
    if not settings.SENDGRID_API_KEY:
        logger.warning("SENDGRID_API_KEY not configured; email not sent")
        return

    subject = f"Red flags observed for patient {submission.patient_id}"
    context = {
        "doctor": doctor,
        "submission": submission,
        "red_flags": red_flags,
        "base_url": settings.SITE_BASE_URL,
    }
    html_content = render_to_string("alerts/email_report.html", context)
    message = Mail(
        from_email=settings.DEFAULT_FROM_EMAIL,
        to_emails=doctor.email,
        subject=subject,
        html_content=html_content,
    )
    try:
        sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
        sg.send(message)
        logger.info("Sent red flag email to %s", doctor.email)
    except Exception as exc:  # pragma: no cover - integration
        logger.exception("Failed to send SendGrid email: %s", exc)
