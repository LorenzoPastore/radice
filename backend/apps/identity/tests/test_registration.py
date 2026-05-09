"""Tests for register_new_user service."""
from unittest.mock import patch

import pytest

from apps.governance.models import AuditLog
from apps.identity.models import Person, User
from apps.identity.services.registration_service import (
    RegistrationError,
    register_new_user,
)


@pytest.mark.django_db
def test_register_new_user_creates_user_and_person():
    user, person = register_new_user(
        email="alice@example.com",
        password="strongpass123",
        given_names="Alice",
        surname="Wonder",
    )
    assert User.objects.filter(pk=user.pk).exists()
    assert Person.objects.filter(pk=person.pk).exists()
    assert user.person_id == person.pk
    assert person.created_by_user_id == user.pk
    assert person.is_living is True


@pytest.mark.django_db
def test_register_new_user_audit_log_entries():
    user, person = register_new_user(
        email="bob@example.com",
        password="strongpass123",
        given_names="Bob",
        surname="Builder",
    )
    user_audits = AuditLog.objects.filter(
        action_type="create_user", entity_id=user.pk
    )
    person_audits = AuditLog.objects.filter(
        action_type="create_person", entity_id=person.pk
    )
    assert user_audits.count() == 1
    assert person_audits.count() == 1
    assert user_audits.first().actor_user_id == user.pk
    assert person_audits.first().actor_user_id == user.pk


@pytest.mark.django_db
def test_register_duplicate_email_raises_error():
    register_new_user(
        email="dup@example.com",
        password="strongpass123",
        given_names="A",
        surname="B",
    )
    with pytest.raises(RegistrationError):
        register_new_user(
            email="dup@example.com",
            password="strongpass123",
            given_names="C",
            surname="D",
        )


@pytest.mark.django_db
def test_register_email_case_insensitive_uniqueness():
    register_new_user(
        email="foo@bar.com",
        password="strongpass123",
        given_names="A",
        surname="B",
    )
    with pytest.raises(RegistrationError):
        register_new_user(
            email="FOO@bar.com",
            password="strongpass123",
            given_names="C",
            surname="D",
        )


@pytest.mark.django_db
def test_register_atomicity():
    """If Person creation fails, User should not be persisted."""
    with patch(
        "apps.identity.services.registration_service.Person.objects.create",
        side_effect=RuntimeError("simulated failure"),
    ):
        with pytest.raises(RuntimeError):
            register_new_user(
                email="atomic@example.com",
                password="strongpass123",
                given_names="A",
                surname="B",
            )
    assert not User.objects.filter(email="atomic@example.com").exists()


@pytest.mark.django_db
def test_register_creates_user_with_unverified_email():
    user, _ = register_new_user(
        email="unverified@example.com",
        password="strongpass123",
        given_names="A",
        surname="B",
    )
    assert user.email_verified_at is None
