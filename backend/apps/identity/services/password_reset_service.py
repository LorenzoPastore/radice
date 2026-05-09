"""Password reset flow — 2-step token-based."""
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from apps.governance.services.audit_service import write_audit
from apps.identity.models import User


class PasswordResetError(Exception):
    """Password reset operation failed."""


PASSWORD_RESET_TOKEN_TTL_HOURS = 1


def request_password_reset(*, email: str) -> None:
    """
    Generate a reset token, save it, and dispatch email.

    SILENT for unknown emails (no leak of registered addresses).
    """
    try:
        user = User.objects.get(email__iexact=email, is_active=True)
    except User.DoesNotExist:
        # Silent: don't reveal whether email is registered
        return

    token = secrets.token_urlsafe(48)
    user.password_reset_token = token
    user.password_reset_sent_at = timezone.now()
    user.save(
        update_fields=[
            "password_reset_token",
            "password_reset_sent_at",
            "updated_at",
        ]
    )

    frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:3000")
    reset_url = f"{frontend_url}/password-reset?token={token}"

    send_mail(
        subject="Reset password — Radice",
        message=(
            f"Ciao {user.display_name},\n\n"
            f"Hai richiesto il reset della password. "
            f"Clicca qui per impostarne una nuova:\n{reset_url}\n\n"
            f"Il link scade tra {PASSWORD_RESET_TOKEN_TTL_HOURS} ora.\n\n"
            f"Se non hai richiesto tu il reset, ignora questa email."
        ),
        from_email=getattr(
            settings, "DEFAULT_FROM_EMAIL", "noreply@radice.local"
        ),
        recipient_list=[user.email],
        fail_silently=False,
    )

    write_audit(action_type="request_password_reset", entity=user, actor=user)


def confirm_password_reset(*, token: str, new_password: str) -> User:
    """
    Validate token and set the new password.
    Invalidates token after use. Revokes all existing auth tokens.
    """
    if len(new_password) < 8:
        raise PasswordResetError("La password deve essere di almeno 8 caratteri")

    try:
        user = User.objects.get(password_reset_token=token)
    except User.DoesNotExist:
        raise PasswordResetError("Token non valido")

    if user.password_reset_sent_at is None:
        raise PasswordResetError("Token corrotto")

    expires_at = user.password_reset_sent_at + timedelta(
        hours=PASSWORD_RESET_TOKEN_TTL_HOURS
    )
    if timezone.now() > expires_at:
        raise PasswordResetError("Token scaduto")

    user.set_password(new_password)
    user.password_reset_token = None
    user.password_reset_sent_at = None
    user.save(
        update_fields=[
            "password",
            "password_reset_token",
            "password_reset_sent_at",
            "updated_at",
        ]
    )

    # Revoke all existing auth tokens (force re-login)
    from rest_framework.authtoken.models import Token as AuthToken

    AuthToken.objects.filter(user=user).delete()

    write_audit(action_type="confirm_password_reset", entity=user, actor=user)

    return user
