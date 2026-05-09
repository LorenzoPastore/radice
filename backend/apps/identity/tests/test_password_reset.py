"""Tests for password reset flow."""
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core import mail
from django.utils import timezone
from rest_framework.authtoken.models import Token

from apps.governance.models import AuditLog
from apps.identity.services.password_reset_service import (
    PASSWORD_RESET_TOKEN_TTL_HOURS,
    PasswordResetError,
    confirm_password_reset,
    request_password_reset,
)
from apps.identity.services.registration_service import register_new_user


@pytest.fixture
def user(db):
    u, _ = register_new_user(
        email="reset@example.com",
        password="oldpassword123",
        given_names="Re",
        surname="Set",
    )
    mail.outbox = []
    return u


@pytest.mark.django_db
def test_request_reset_for_existing_user_sends_email(user):
    request_password_reset(email="reset@example.com")
    assert len(mail.outbox) == 1
    msg = mail.outbox[0]
    assert "reset@example.com" in msg.to
    assert "password-reset?token=" in msg.body


@pytest.mark.django_db
def test_request_reset_for_unknown_email_silent(db):
    """No error, no email — never leak whether email is registered."""
    request_password_reset(email="ghost@example.com")
    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_request_reset_sets_token_and_timestamp(user):
    request_password_reset(email="reset@example.com")
    user.refresh_from_db()
    assert user.password_reset_token is not None
    assert len(user.password_reset_token) >= 32
    assert user.password_reset_sent_at is not None


@pytest.mark.django_db
def test_confirm_reset_with_valid_token_sets_new_password(user):
    request_password_reset(email="reset@example.com")
    user.refresh_from_db()
    token = user.password_reset_token

    confirm_password_reset(token=token, new_password="brandnewpass123")

    user.refresh_from_db()
    assert user.check_password("brandnewpass123")
    assert not user.check_password("oldpassword123")


@pytest.mark.django_db
def test_confirm_reset_invalidates_token(user):
    request_password_reset(email="reset@example.com")
    user.refresh_from_db()
    token = user.password_reset_token
    confirm_password_reset(token=token, new_password="brandnewpass123")
    user.refresh_from_db()
    assert user.password_reset_token is None
    assert user.password_reset_sent_at is None


@pytest.mark.django_db
def test_confirm_reset_revokes_existing_auth_tokens(user):
    Token.objects.create(user=user)
    request_password_reset(email="reset@example.com")
    user.refresh_from_db()
    token = user.password_reset_token

    confirm_password_reset(token=token, new_password="brandnewpass123")

    assert not Token.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_confirm_reset_with_expired_token_raises(user):
    request_password_reset(email="reset@example.com")
    user.refresh_from_db()
    token = user.password_reset_token

    future = timezone.now() + timedelta(
        hours=PASSWORD_RESET_TOKEN_TTL_HOURS + 1
    )
    with patch(
        "apps.identity.services.password_reset_service.timezone.now",
        return_value=future,
    ):
        with pytest.raises(PasswordResetError):
            confirm_password_reset(token=token, new_password="brandnewpass123")


@pytest.mark.django_db
def test_confirm_reset_with_invalid_token_raises(db):
    with pytest.raises(PasswordResetError):
        confirm_password_reset(token="nope", new_password="brandnewpass123")


@pytest.mark.django_db
def test_confirm_reset_password_too_short_raises(user):
    request_password_reset(email="reset@example.com")
    user.refresh_from_db()
    token = user.password_reset_token

    with pytest.raises(PasswordResetError):
        confirm_password_reset(token=token, new_password="short")


@pytest.mark.django_db
def test_confirm_reset_creates_audit_log_entry(user):
    request_password_reset(email="reset@example.com")
    user.refresh_from_db()
    token = user.password_reset_token
    confirm_password_reset(token=token, new_password="brandnewpass123")
    assert AuditLog.objects.filter(
        action_type="confirm_password_reset", entity_id=user.pk
    ).exists()


@pytest.mark.django_db
def test_request_reset_creates_audit_log_entry(user):
    request_password_reset(email="reset@example.com")
    assert AuditLog.objects.filter(
        action_type="request_password_reset", entity_id=user.pk
    ).exists()
