"""Tests for email verification flow."""
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core import mail
from django.utils import timezone

from apps.governance.models import AuditLog
from apps.identity.models import User
from apps.identity.services.email_verification_service import (
    VERIFICATION_TOKEN_TTL_HOURS,
    VerificationError,
    send_verification_email,
    verify_email,
)
from apps.identity.services.registration_service import register_new_user


@pytest.fixture
def fresh_user(db):
    user, _ = register_new_user(
        email="ver@example.com",
        password="strongpass123",
        given_names="Ver",
        surname="User",
    )
    mail.outbox = []  # registration may have sent something via service path
    return user


@pytest.mark.django_db
def test_send_verification_email_sets_token_and_timestamp(fresh_user):
    send_verification_email(fresh_user)
    fresh_user.refresh_from_db()
    assert fresh_user.email_verification_token is not None
    assert len(fresh_user.email_verification_token) >= 32
    assert fresh_user.email_verification_sent_at is not None


@pytest.mark.django_db
def test_send_verification_email_dispatches_email(fresh_user):
    send_verification_email(fresh_user)
    assert len(mail.outbox) == 1
    msg = mail.outbox[0]
    assert fresh_user.email in msg.to
    assert "verify-email?token=" in msg.body


@pytest.mark.django_db
def test_verify_email_with_valid_token_marks_verified(fresh_user):
    send_verification_email(fresh_user)
    fresh_user.refresh_from_db()
    token = fresh_user.email_verification_token
    user = verify_email(token=token)
    assert user.email_verified_at is not None


@pytest.mark.django_db
def test_verify_email_invalidates_token_after_use(fresh_user):
    send_verification_email(fresh_user)
    fresh_user.refresh_from_db()
    token = fresh_user.email_verification_token
    verify_email(token=token)
    fresh_user.refresh_from_db()
    assert fresh_user.email_verification_token is None


@pytest.mark.django_db
def test_verify_email_with_invalid_token_raises():
    with pytest.raises(VerificationError):
        verify_email(token="not-a-real-token")


@pytest.mark.django_db
def test_verify_email_with_expired_token_raises(fresh_user):
    send_verification_email(fresh_user)
    fresh_user.refresh_from_db()
    token = fresh_user.email_verification_token

    future = timezone.now() + timedelta(hours=VERIFICATION_TOKEN_TTL_HOURS + 1)
    with patch(
        "apps.identity.services.email_verification_service.timezone.now",
        return_value=future,
    ):
        with pytest.raises(VerificationError):
            verify_email(token=token)


@pytest.mark.django_db
def test_verify_email_idempotent_if_already_verified(fresh_user):
    send_verification_email(fresh_user)
    fresh_user.refresh_from_db()
    token = fresh_user.email_verification_token
    verify_email(token=token)
    # token cleared, but the User is already verified — calling again with same
    # token now raises (token=None lookup), but second call on a re-tokenized
    # user that's already verified should be a no-op. Simulate by re-setting.
    fresh_user.refresh_from_db()
    fresh_user.email_verification_token = "second-token"
    fresh_user.email_verification_sent_at = timezone.now()
    fresh_user.save(
        update_fields=[
            "email_verification_token",
            "email_verification_sent_at",
            "updated_at",
        ]
    )
    user_again = verify_email(token="second-token")
    assert user_again.email_verified_at is not None


@pytest.mark.django_db
def test_verify_email_writes_audit_log(fresh_user):
    send_verification_email(fresh_user)
    fresh_user.refresh_from_db()
    token = fresh_user.email_verification_token
    verify_email(token=token)
    assert AuditLog.objects.filter(
        action_type="verify_email", entity_id=fresh_user.pk
    ).exists()
