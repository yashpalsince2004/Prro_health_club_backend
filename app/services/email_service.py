"""
Email service using Resend API with Jinja2 HTML templates.

Architecture:
- render_template(): loads and renders a Jinja2 template
- send_email(): low-level Resend API call with retry logic
- send_X(): high-level functions called by other services/endpoints via BackgroundTasks
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
# pyrefly: ignore [missing-import]
import resend
# pyrefly: ignore [missing-import]
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pathlib import Path
# pyrefly: ignore [missing-import]
from loguru import logger
from app.core.config import settings

# Template loader — resolves to app/templates/email/
TEMPLATE_DIR = Path(__file__).parent.parent / "templates" / "email"
jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(["html"])
)

def _get_base_context() -> dict:
    """Returns the common template variables injected into every email."""
    return {
        "gym_name": "Prro Health Club",
        "gym_address": settings.GYM_ADDRESS,
        "gym_phone": settings.GYM_PHONE,
        "gym_email": settings.GYM_EMAIL,
        "frontend_url": settings.FRONTEND_URL,
    }

def _render_template(template_name: str, context: dict) -> str:
    """Renders a Jinja2 email template with merged base context."""
    template = jinja_env.get_template(template_name)
    return template.render(**_get_base_context(), **context)

def _send_email(to_email: str, subject: str, html_content: str) -> bool:
    """
    Core Resend API call with retry logic.
    Returns True on success, False on all failures.
    Never raises exceptions.
    """
    if not settings.ENABLE_EMAILS:
        logger.info(f"[Email] ENABLE_EMAILS=False — skipped send to {to_email}: {subject}")
        return True

    if not settings.RESEND_API_KEY:
        logger.warning("[Email] RESEND_API_KEY not configured — skipping email send")
        return False

    resend.api_key = settings.RESEND_API_KEY

    for attempt in range(1, settings.EMAIL_RETRY_COUNT + 1):
        try:
            resend.Emails.send({
                "from": f"{settings.FROM_NAME} <{settings.FROM_EMAIL}>",
                "to": [to_email],
                "subject": subject,
                "html": html_content,
            })
            logger.info(f"[Email] Sent '{subject}' to {to_email}")
            return True
        except Exception as e:
            logger.warning(f"[Email] Attempt {attempt}/{settings.EMAIL_RETRY_COUNT} failed: {e}")

    logger.error(f"[Email] All {settings.EMAIL_RETRY_COUNT} attempts failed for {to_email}")
    return False

# --- High-level send functions ---

def send_welcome_email(to_email: str, member_name: str, temp_password: str = None) -> bool:
    html = _render_template("welcome.html", {
        "subject": "Welcome to Prro Health Club!",
        "member_name": member_name,
        "email": to_email,
        "temp_password": temp_password,
    })
    return _send_email(to_email, "Welcome to Prro Health Club! 💪", html)

def send_payment_receipt_email(
    to_email: str,
    member_name: str,
    receipt_number: str,
    plan_name: str,
    duration_days: int,
    membership_start: date,
    membership_end: date,
    amount_paid: Decimal,
    payment_method: str,
    transaction_reference: Optional[str],
    payment_date: datetime,
    discount_percent: float = 0.0,
) -> bool:
    subtotal = amount_paid
    discount_amount = subtotal * Decimal(str(discount_percent / 100))
    taxable = subtotal - discount_amount
    gst_amount = taxable * Decimal(str(settings.GYM_GST_PERCENT / 100))
    total = taxable + gst_amount

    html = _render_template("payment_receipt.html", {
        "subject": f"Payment Receipt - {receipt_number}",
        "member_name": member_name,
        "receipt_number": receipt_number,
        "plan_name": plan_name,
        "duration_days": duration_days,
        "membership_start": membership_start.strftime("%d %b %Y"),
        "membership_end": membership_end.strftime("%d %b %Y"),
        "subtotal": f"₹{subtotal:,.2f}",
        "discount_percent": discount_percent,
        "discount_amount": f"₹{discount_amount:,.2f}",
        "gst_percent": settings.GYM_GST_PERCENT,
        "gst_number": settings.GYM_GST_NUMBER or "N/A",
        "gst_amount": f"₹{gst_amount:,.2f}",
        "total": f"₹{total:,.2f}",
        "payment_method": payment_method.upper(),
        "transaction_reference": transaction_reference or "N/A",
        "payment_date": payment_date.strftime("%d %b %Y, %I:%M %p"),
    })
    return _send_email(to_email, f"Payment Receipt — {receipt_number}", html)

def send_membership_expiry_reminder(
    to_email: str, member_name: str, plan_name: str,
    end_date: date, days_remaining: int
) -> bool:
    html = _render_template("membership_expiry.html", {
        "subject": f"Your membership expires in {days_remaining} days",
        "member_name": member_name,
        "plan_name": plan_name,
        "end_date": end_date.strftime("%d %b %Y"),
        "days_remaining": days_remaining,
    })
    return _send_email(to_email, f"⚠️ Membership expiring in {days_remaining} days — Prro Health Club", html)

def send_membership_expired_email(
    to_email: str, member_name: str, plan_name: str, expired_on: date
) -> bool:
    html = _render_template("membership_expired.html", {
        "subject": "Your Prro Health Club membership has expired",
        "member_name": member_name,
        "plan_name": plan_name,
        "expired_on": expired_on.strftime("%d %b %Y"),
    })
    return _send_email(to_email, "Your membership has expired — Prro Health Club", html)

def send_password_reset_email(
    to_email: str, member_name: str, reset_url: str
) -> bool:
    # NEVER log the reset_url — it contains the token
    html = _render_template("password_reset.html", {
        "subject": "Reset your Prro Health Club password",
        "member_name": member_name,
        "reset_url": reset_url,
        "expiry_minutes": settings.RESET_TOKEN_EXPIRY_MINUTES,
    })
    return _send_email(to_email, "Reset your password — Prro Health Club", html)
