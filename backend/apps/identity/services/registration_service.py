"""Registration flows for new users.

Implements the User <-> Person creation transactionally per
apps/identity/CLAUDE.md vincolo 2 (every User must have a Person).
"""
import secrets
from typing import Optional

from django.db import transaction

from apps.governance.services.audit_service import write_audit
from apps.identity.models import Person, User


class RegistrationError(Exception):
    """Domain error raised when registration fails."""


@transaction.atomic
def register_new_user(
    *,
    email: str,
    password: str,
    given_names: str,
    surname: str,
    display_name: Optional[str] = None,
    locale: str = "it-IT",
    timezone_name: str = "Europe/Rome",
) -> tuple[User, Person]:
    """
    Register a brand-new user (no pre-existing Person).

    Atomically creates User + Person + bidirectional link.
    Writes audit log entries for both.

    Returns:
        (user, person) tuple

    Raises:
        RegistrationError: if email already exists or validation fails.
    """
    if User.objects.filter(email__iexact=email).exists():
        raise RegistrationError(f"Email already registered: {email}")

    # 1. Create User without Person link (will set after)
    user = User.objects.create_user(
        email=email,
        password=password,
        display_name=display_name or f"{given_names} {surname}".strip(),
        locale=locale,
        timezone=timezone_name,
    )

    # 2. Create Person, attributed to the new user
    person = Person.objects.create(
        given_names=given_names,
        surname=surname,
        is_living=True,
        created_by_user=user,
    )

    # 3. Link User -> Person (the canonical link)
    user.person = person
    user.save(update_fields=["person", "updated_at"])

    # 4. Audit log entries
    write_audit(action_type="create_user", entity=user, actor=user)
    write_audit(action_type="create_person", entity=person, actor=user)

    return user, person


def generate_email_verification_token() -> str:
    """Cryptographically random URL-safe token."""
    return secrets.token_urlsafe(48)
