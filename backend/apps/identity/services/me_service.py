"""Services for the authenticated user's own data (`/api/me/`)."""
from typing import Any

from django.db import transaction

from apps.governance.services.audit_service import write_audit
from apps.identity.models import Person, User

USER_EDITABLE_FIELDS = {
    "display_name",
    "locale",
    "timezone",
    "privacy_preset",
    "notification_preferences",
}

PERSON_SELF_EDITABLE_FIELDS = {
    "given_names",
    "surname",
    "surname_at_birth",
    "nicknames",
    "birth_date",
    "birth_date_precision",
    "birth_place",
    "gender",
    "short_bio",
}


@transaction.atomic
def update_me_user(*, user: User, changes: dict[str, Any]) -> User:
    """Update User-level fields for self.

    Only fields in USER_EDITABLE_FIELDS are accepted. Writes audit log
    with diff before/after.
    """
    valid_changes = {k: v for k, v in changes.items() if k in USER_EDITABLE_FIELDS}
    if not valid_changes:
        return user

    before = {k: getattr(user, k) for k in valid_changes}

    for k, v in valid_changes.items():
        setattr(user, k, v)
    user.save()

    write_audit(
        action_type="update_user_self",
        entity=user,
        actor=user,
        changes_diff={"before": before, "after": valid_changes},
    )
    return user


@transaction.atomic
def update_me_person(*, user: User, changes: dict[str, Any]) -> Person:
    """Update self-Person fields. Caller's Person must exist.

    Only fields in PERSON_SELF_EDITABLE_FIELDS are accepted. Writes audit
    log with diff before/after.
    """
    person = user.person
    if person is None:
        raise ValueError("User has no associated Person")

    valid_changes = {
        k: v for k, v in changes.items() if k in PERSON_SELF_EDITABLE_FIELDS
    }
    if not valid_changes:
        return person

    before = {k: getattr(person, k) for k in valid_changes}

    for k, v in valid_changes.items():
        setattr(person, k, v)
    person.save()

    write_audit(
        action_type="update_person_self",
        entity=person,
        actor=user,
        changes_diff={"before": before, "after": valid_changes},
    )
    return person


@transaction.atomic
def change_password(
    *,
    user: User,
    current_password: str,
    new_password: str,
    current_token_key: str | None = None,
) -> User:
    """Change the user's password after verifying current_password.

    Revokes all auth tokens EXCEPT the current one (so the user is not
    logged out). Writes audit log entry.
    """
    if not user.check_password(current_password):
        raise ValueError("Password attuale non corretta")
    if len(new_password) < 8:
        raise ValueError("La nuova password deve essere di almeno 8 caratteri")
    if user.check_password(new_password):
        raise ValueError("La nuova password deve essere diversa da quella attuale")

    user.set_password(new_password)
    user.save(update_fields=["password", "updated_at"])

    # Revoke all OTHER tokens (preserve current session if provided).
    from rest_framework.authtoken.models import Token

    qs = Token.objects.filter(user=user)
    if current_token_key:
        qs = qs.exclude(key=current_token_key)
    qs.delete()

    write_audit(action_type="change_password", entity=user, actor=user)
    return user
