"""Login/logout services."""
from typing import Optional

from django.contrib.auth import authenticate
from django.utils import timezone
from rest_framework.authtoken.models import Token

from apps.governance.services.audit_service import write_audit
from apps.identity.models import User


class AuthError(Exception):
    """Authentication failed."""


def login_user(*, email: str, password: str) -> tuple[User, str]:
    """
    Authenticate a user by email + password.

    Returns (user, token_key) on success.
    Raises AuthError on bad credentials or inactive user.

    Email-verification is NOT enforced here: unverified users are allowed
    to login so the frontend can route them to a "verify your email" page.
    The verification status is exposed by the view in the response payload.
    """
    user: Optional[User] = authenticate(username=email, password=password)
    if user is None:
        # Don't reveal whether email exists
        raise AuthError("Email o password non corretti")

    if not user.is_active:
        raise AuthError("Account disattivato")

    user.last_login_at = timezone.now()
    user.save(update_fields=["last_login_at", "updated_at"])

    token, _created = Token.objects.get_or_create(user=user)

    write_audit(action_type="login", entity=user, actor=user)

    return user, token.key


def logout_user(*, user: User) -> None:
    """Revoke the user's token (logout). Idempotent."""
    Token.objects.filter(user=user).delete()
    write_audit(action_type="logout", entity=user, actor=user)
