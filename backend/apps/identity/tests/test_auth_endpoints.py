"""DRF endpoint tests for login / logout / password reset."""
import pytest
from django.core import mail
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.identity.services.password_reset_service import request_password_reset
from apps.identity.services.registration_service import register_new_user


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def user(db):
    u, _ = register_new_user(
        email="api@example.com",
        password="strongpass123",
        given_names="Api",
        surname="User",
    )
    mail.outbox = []
    return u


@pytest.mark.django_db
def test_login_endpoint_success(client, user):
    url = reverse("identity:login")
    resp = client.post(
        url,
        {"email": "api@example.com", "password": "strongpass123"},
        format="json",
    )
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert "token" in body and len(body["token"]) > 0
    assert body["user"]["email"] == "api@example.com"
    assert body["email_verified"] is False


@pytest.mark.django_db
def test_login_endpoint_bad_credentials_401(client, user):
    url = reverse("identity:login")
    resp = client.post(
        url,
        {"email": "api@example.com", "password": "wrongpass"},
        format="json",
    )
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_logout_endpoint_with_valid_token_204(client, user):
    token = Token.objects.create(user=user)
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    url = reverse("identity:logout")
    resp = client.post(url)
    assert resp.status_code == status.HTTP_204_NO_CONTENT
    assert not Token.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_logout_endpoint_unauthenticated_401(client):
    url = reverse("identity:logout")
    resp = client.post(url)
    assert resp.status_code in (
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    )


@pytest.mark.django_db
def test_password_reset_request_endpoint_always_200(client, db):
    """Even for unknown emails, response must be 200 (anti-leak)."""
    url = reverse("identity:password-reset-request")
    resp = client.post(url, {"email": "ghost@example.com"}, format="json")
    assert resp.status_code == status.HTTP_200_OK
    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_password_reset_request_endpoint_sends_email_for_known(client, user):
    url = reverse("identity:password-reset-request")
    resp = client.post(url, {"email": "api@example.com"}, format="json")
    assert resp.status_code == status.HTTP_200_OK
    assert any("api@example.com" in m.to for m in mail.outbox)


@pytest.mark.django_db
def test_password_reset_confirm_endpoint_success(client, user):
    request_password_reset(email="api@example.com")
    user.refresh_from_db()
    url = reverse("identity:password-reset-confirm")
    resp = client.post(
        url,
        {
            "token": user.password_reset_token,
            "new_password": "brandnewpass123",
        },
        format="json",
    )
    assert resp.status_code == status.HTTP_200_OK
    user.refresh_from_db()
    assert user.check_password("brandnewpass123")


@pytest.mark.django_db
def test_password_reset_confirm_endpoint_bad_token_400(client, db):
    url = reverse("identity:password-reset-confirm")
    resp = client.post(
        url,
        {"token": "garbage", "new_password": "brandnewpass123"},
        format="json",
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_password_reset_confirm_endpoint_short_password_400(client, user):
    request_password_reset(email="api@example.com")
    user.refresh_from_db()
    url = reverse("identity:password-reset-confirm")
    resp = client.post(
        url,
        {"token": user.password_reset_token, "new_password": "short"},
        format="json",
    )
    # Caught either by serializer min_length or the service check.
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
