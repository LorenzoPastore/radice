"""DRF endpoint tests for register / verify-email."""
import pytest
from django.core import mail
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.identity.models import User
from apps.identity.services.email_verification_service import (
    send_verification_email,
)
from apps.identity.services.registration_service import register_new_user


@pytest.fixture
def client():
    return APIClient()


@pytest.mark.django_db
def test_post_register_returns_201_with_user_and_person(client):
    url = reverse("identity:register")
    payload = {
        "email": "api1@example.com",
        "password": "strongpass123",
        "given_names": "Api",
        "surname": "One",
    }
    resp = client.post(url, payload, format="json")
    assert resp.status_code == status.HTTP_201_CREATED
    body = resp.json()
    assert body["user"]["email"] == "api1@example.com"
    assert body["person"]["given_names"] == "Api"
    assert body["person"]["surname"] == "One"


@pytest.mark.django_db
def test_post_register_returns_400_on_duplicate_email(client):
    url = reverse("identity:register")
    payload = {
        "email": "dup@example.com",
        "password": "strongpass123",
        "given_names": "A",
        "surname": "B",
    }
    client.post(url, payload, format="json")
    resp = client.post(url, payload, format="json")
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_post_register_returns_400_on_weak_password(client):
    url = reverse("identity:register")
    payload = {
        "email": "weak@example.com",
        "password": "password",
        "given_names": "A",
        "surname": "B",
    }
    resp = client.post(url, payload, format="json")
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_post_register_sends_verification_email(client):
    mail.outbox = []
    url = reverse("identity:register")
    payload = {
        "email": "mail@example.com",
        "password": "strongpass123",
        "given_names": "M",
        "surname": "Ail",
    }
    resp = client.post(url, payload, format="json")
    assert resp.status_code == status.HTTP_201_CREATED
    assert any("mail@example.com" in m.to for m in mail.outbox)


@pytest.mark.django_db
def test_post_register_no_authentication_required(client):
    """Endpoint must be reachable without any credentials."""
    client.credentials()  # ensure no auth
    url = reverse("identity:register")
    resp = client.post(
        url,
        {
            "email": "anon@example.com",
            "password": "strongpass123",
            "given_names": "A",
            "surname": "N",
        },
        format="json",
    )
    assert resp.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db
def test_post_verify_email_with_valid_token_returns_200(client):
    user, _ = register_new_user(
        email="vapi@example.com",
        password="strongpass123",
        given_names="V",
        surname="Api",
    )
    send_verification_email(user)
    user.refresh_from_db()
    url = reverse("identity:verify-email")
    resp = client.post(url, {"token": user.email_verification_token}, format="json")
    assert resp.status_code == status.HTTP_200_OK
    user.refresh_from_db()
    assert user.email_verified_at is not None


@pytest.mark.django_db
def test_post_verify_email_with_invalid_token_returns_400(client):
    url = reverse("identity:verify-email")
    resp = client.post(url, {"token": "garbage"}, format="json")
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
