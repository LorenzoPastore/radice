"""Tests for login/logout services."""
import pytest
from rest_framework.authtoken.models import Token

from apps.governance.models import AuditLog
from apps.identity.services.auth_service import (
    AuthError,
    login_user,
    logout_user,
)
from apps.identity.services.registration_service import register_new_user


@pytest.fixture
def user(db):
    u, _ = register_new_user(
        email="login@example.com",
        password="strongpass123",
        given_names="Log",
        surname="User",
    )
    return u


@pytest.mark.django_db
def test_login_with_valid_credentials_returns_token(user):
    u, token = login_user(email="login@example.com", password="strongpass123")
    assert u.pk == user.pk
    assert isinstance(token, str) and len(token) > 0
    assert Token.objects.filter(user=user, key=token).exists()


@pytest.mark.django_db
def test_login_with_invalid_password_returns_401(user):
    with pytest.raises(AuthError):
        login_user(email="login@example.com", password="wrongpass")


@pytest.mark.django_db
def test_login_with_unknown_email_returns_401_same_message(user):
    """Anti-leak: same error for unknown email and bad password."""
    try:
        login_user(email="nope@example.com", password="strongpass123")
        raised_unknown = None
    except AuthError as e:
        raised_unknown = str(e)

    try:
        login_user(email="login@example.com", password="wrongpass")
        raised_bad = None
    except AuthError as e:
        raised_bad = str(e)

    assert raised_unknown == raised_bad
    assert raised_unknown is not None


@pytest.mark.django_db
def test_login_inactive_user_returns_401(user):
    user.is_active = False
    user.save(update_fields=["is_active", "updated_at"])
    with pytest.raises(AuthError):
        login_user(email="login@example.com", password="strongpass123")


@pytest.mark.django_db
def test_login_unverified_user_can_login_but_flag_set(user):
    """Unverified email is permitted at the service layer; views surface flag."""
    assert user.email_verified_at is None
    u, token = login_user(email="login@example.com", password="strongpass123")
    assert token
    assert u.email_verified_at is None


@pytest.mark.django_db
def test_login_creates_audit_log_entry(user):
    login_user(email="login@example.com", password="strongpass123")
    assert AuditLog.objects.filter(
        action_type="login", entity_id=user.pk
    ).exists()


@pytest.mark.django_db
def test_login_updates_last_login_at(user):
    assert user.last_login_at is None
    login_user(email="login@example.com", password="strongpass123")
    user.refresh_from_db()
    assert user.last_login_at is not None


@pytest.mark.django_db
def test_login_returns_existing_token_if_present(user):
    existing = Token.objects.create(user=user)
    _, token = login_user(email="login@example.com", password="strongpass123")
    assert token == existing.key
    assert Token.objects.filter(user=user).count() == 1


@pytest.mark.django_db
def test_logout_revokes_token(user):
    Token.objects.create(user=user)
    logout_user(user=user)
    assert not Token.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_logout_creates_audit_log_entry(user):
    Token.objects.create(user=user)
    logout_user(user=user)
    assert AuditLog.objects.filter(
        action_type="logout", entity_id=user.pk
    ).exists()


@pytest.mark.django_db
def test_logout_idempotent(user):
    """Logout without an existing token must not error."""
    assert not Token.objects.filter(user=user).exists()
    logout_user(user=user)  # no token
    logout_user(user=user)  # second call, still no token
    assert not Token.objects.filter(user=user).exists()
