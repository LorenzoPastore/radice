"""Email verification flow — minimal token-based."""
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from apps.governance.services.audit_service import write_audit
from apps.identity.models import User
from apps.identity.services.registration_service import (
    generate_email_verification_token,
)


class VerificationError(Exception):
    """Raised when verification fails (token invalid, expired, etc.)."""


VERIFICATION_TOKEN_TTL_HOURS = 48


def send_verification_email(user: User) -> User:
    """
    Generate a fresh token, save it on the user, and dispatch verification email.
    """
    token = generate_email_verification_token()
    user.email_verification_token = token
    user.email_verification_sent_at = timezone.now()
    user.save(
        update_fields=[
            "email_verification_token",
            "email_verification_sent_at",
            "updated_at",
        ]
    )

    frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:3000")
    verify_url = f"{frontend_url}/verify-email?token={token}"

    send_mail(
        subject="Verifica il tuo indirizzo email — Radice",
        message=(
            f"Ciao {user.display_name},\n\n"
            f"Per verificare il tuo indirizzo email, clicca qui:\n{verify_url}\n\n"
            f"Il link scade tra {VERIFICATION_TOKEN_TTL_HOURS} ore.\n\n"
            f"Se non hai richiesto tu la registrazione, ignora questa email."
        ),
        from_email=getattr(
            settings, "DEFAULT_FROM_EMAIL", "noreply@radice.local"
        ),
        recipient_list=[user.email],
        fail_silently=False,
    )
    return user


def verify_email(*, token: str) -> User:
    """
    Mark a user's email as verified using their one-time token.
    Returns the User on success. Raises VerificationError on failure.
    """
    try:
        user = User.objects.get(email_verification_token=token)
    except User.DoesNotExist:
        raise VerificationError("Token non valido")

    if user.email_verified_at is not None:
        # Already verified, idempotent
        return user

    if user.email_verification_sent_at is None:
        raise VerificationError("Token corrotto")

    expires_at = user.email_verification_sent_at + timedelta(
        hours=VERIFICATION_TOKEN_TTL_HOURS
    )
    if timezone.now() > expires_at:
        raise VerificationError("Token scaduto")

    user.email_verified_at = timezone.now()
    user.email_verification_token = None  # invalidate
    user.save(
        update_fields=[
            "email_verified_at",
            "email_verification_token",
            "updated_at",
        ]
    )

    write_audit(action_type="verify_email", entity=user, actor=user)
    return user
