"""Factory-boy factories for identity models. Used in tests."""

import datetime

import factory
from django.utils import timezone
from factory.django import DjangoModelFactory

from .models import Invitation, Person, PersonClaim, User


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User
        django_get_or_create = ("email",)
        skip_postgeneration_save = True

    email = factory.Sequence(lambda n: f"user{n}@radice.test")
    display_name = factory.Faker("name", locale="it_IT")

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        password = kwargs.pop("password", "testpass123")
        user = model_class.objects.create_user(*args, password=password, **kwargs)
        return user


class PersonFactory(DjangoModelFactory):
    class Meta:
        model = Person

    given_names = factory.Faker("first_name", locale="it_IT")
    surname = factory.Faker("last_name", locale="it_IT")
    is_living = True
    created_by_user = factory.SubFactory(UserFactory)


class PersonClaimFactory(DjangoModelFactory):
    class Meta:
        model = PersonClaim

    person = factory.SubFactory(PersonFactory)
    claiming_user = factory.SubFactory(UserFactory)


class InvitationFactory(DjangoModelFactory):
    class Meta:
        model = Invitation

    invited_email = factory.Sequence(lambda n: f"invite{n}@radice.test")
    inviter_user = factory.SubFactory(UserFactory)
    token = factory.Sequence(lambda n: f"tok_{n:032d}")
    expires_at = factory.LazyFunction(
        lambda: timezone.now() + datetime.timedelta(days=7)
    )
