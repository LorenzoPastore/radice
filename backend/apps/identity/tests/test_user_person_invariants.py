"""Tests sui vincoli fondamentali del dominio identity."""

import datetime

import pytest
from django.db import IntegrityError, transaction

from apps.identity.factories import (
    InvitationFactory,
    PersonClaimFactory,
    PersonFactory,
    UserFactory,
)
from apps.identity.models import Invitation, Person, PersonClaim, User


@pytest.mark.django_db
class TestUser:
    def test_user_creation_with_email_and_password(self):
        user = User.objects.create_user(
            email="alice@radice.test",
            password="strongpass1",
            display_name="Alice",
        )
        assert user.pk is not None
        assert user.email == "alice@radice.test"
        assert user.check_password("strongpass1") is True
        assert user.display_name == "Alice"

    def test_user_email_unique(self):
        User.objects.create_user(email="dup@radice.test", password="p", display_name="A")
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                User.objects.create_user(
                    email="dup@radice.test", password="q", display_name="B"
                )

    def test_user_set_unusable_password(self):
        user = User.objects.create_user(
            email="oauth@radice.test",
            display_name="OAuth User",
        )
        assert user.has_usable_password() is False


@pytest.mark.django_db
class TestPerson:
    def test_person_with_minimal_fields(self):
        creator = UserFactory()
        p = Person.objects.create(
            given_names="Mario",
            surname="Rossi",
            is_living=True,
            created_by_user=creator,
        )
        assert p.pk is not None

    def test_person_dead_requires_death_date(self):
        creator = UserFactory()
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                Person.objects.create(
                    given_names="Giuseppe",
                    surname="Verdi",
                    is_living=False,
                    death_date=None,
                    created_by_user=creator,
                )

    def test_person_birth_before_death(self):
        creator = UserFactory()
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                Person.objects.create(
                    given_names="Bad",
                    surname="Dates",
                    is_living=False,
                    birth_date=datetime.date(2000, 1, 1),
                    death_date=datetime.date(1990, 1, 1),
                    created_by_user=creator,
                )

    def test_person_dead_with_death_date_ok(self):
        creator = UserFactory()
        p = Person.objects.create(
            given_names="Late",
            surname="Person",
            is_living=False,
            birth_date=datetime.date(1900, 1, 1),
            death_date=datetime.date(1980, 6, 15),
            created_by_user=creator,
        )
        assert p.pk is not None


@pytest.mark.django_db
class TestPersonClaim:
    def test_personclaim_unique_pending_per_person_user(self):
        person = PersonFactory()
        user = UserFactory()
        PersonClaimFactory(person=person, claiming_user=user)
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                PersonClaimFactory(person=person, claiming_user=user)

    def test_personclaim_can_have_multiple_resolved(self):
        person = PersonFactory()
        user = UserFactory()
        PersonClaimFactory(
            person=person,
            claiming_user=user,
            status=PersonClaim.Status.REJECTED,
        )
        # Now a new pending one is allowed since the previous is not pending
        new_pending = PersonClaimFactory(person=person, claiming_user=user)
        assert new_pending.status == PersonClaim.Status.PENDING


@pytest.mark.django_db
class TestInvitation:
    def test_invitation_token_unique(self):
        InvitationFactory(token="duptoken123")
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                InvitationFactory(token="duptoken123")
