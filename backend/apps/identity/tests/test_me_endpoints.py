"""DRF endpoint tests for /api/me/ — self profile + change password."""
import datetime

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.governance.models import AuditLog
from apps.identity.services.registration_service import register_new_user


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def user(db):
    u, _ = register_new_user(
        email="me@example.com",
        password="strongpass123",
        given_names="Me",
        surname="User",
    )
    return u


@pytest.fixture
def auth_client(client, user):
    token = Token.objects.create(user=user)
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    client._token = token  # stash for tests that need the key
    return client


# ---------------------------------------------------------------------------
# GET /api/me/
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_get_me_returns_user_and_person(auth_client, user):
    resp = auth_client.get(reverse("identity:me"))
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert body["user"]["email"] == "me@example.com"
    assert body["user"]["id"] == str(user.id)
    assert body["person"] is not None
    assert body["person"]["given_names"] == "Me"
    assert body["person"]["surname"] == "User"


@pytest.mark.django_db
def test_get_me_unauthenticated_returns_401_or_403(client):
    resp = client.get(reverse("identity:me"))
    assert resp.status_code in (
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    )


@pytest.mark.django_db
def test_get_me_includes_email_verified_at(auth_client, user):
    resp = auth_client.get(reverse("identity:me"))
    body = resp.json()
    assert "email_verified_at" in body["user"]
    # Newly registered → not yet verified
    assert body["user"]["email_verified_at"] is None


@pytest.mark.django_db
def test_get_me_does_not_leak_password_field(auth_client):
    resp = auth_client.get(reverse("identity:me"))
    body = resp.json()
    assert "password" not in body["user"]


# ---------------------------------------------------------------------------
# PATCH /api/me/
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_patch_me_updates_display_name(auth_client, user):
    resp = auth_client.patch(
        reverse("identity:me"),
        {"display_name": "Brand New Name"},
        format="json",
    )
    assert resp.status_code == status.HTTP_200_OK
    user.refresh_from_db()
    assert user.display_name == "Brand New Name"


@pytest.mark.django_db
def test_patch_me_updates_locale_and_timezone(auth_client, user):
    resp = auth_client.patch(
        reverse("identity:me"),
        {"locale": "en-US", "timezone": "America/New_York"},
        format="json",
    )
    assert resp.status_code == status.HTTP_200_OK
    user.refresh_from_db()
    assert user.locale == "en-US"
    assert user.timezone == "America/New_York"


@pytest.mark.django_db
def test_patch_me_updates_privacy_preset(auth_client, user):
    resp = auth_client.patch(
        reverse("identity:me"),
        {"privacy_preset": "open"},
        format="json",
    )
    assert resp.status_code == status.HTTP_200_OK
    user.refresh_from_db()
    assert user.privacy_preset == "open"


@pytest.mark.django_db
def test_patch_me_invalid_privacy_preset_returns_400(auth_client):
    resp = auth_client.patch(
        reverse("identity:me"),
        {"privacy_preset": "totally-not-a-choice"},
        format="json",
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_patch_me_ignores_email_field(auth_client, user):
    auth_client.patch(
        reverse("identity:me"),
        {"email": "hacker@evil.com", "display_name": "x"},
        format="json",
    )
    user.refresh_from_db()
    assert user.email == "me@example.com"


@pytest.mark.django_db
def test_patch_me_ignores_password_field(auth_client, user):
    original_hash = user.password
    auth_client.patch(
        reverse("identity:me"),
        {"password": "newhackedpass", "display_name": "x"},
        format="json",
    )
    user.refresh_from_db()
    assert user.password == original_hash


@pytest.mark.django_db
def test_patch_me_creates_audit_log_entry(auth_client, user):
    pre = AuditLog.objects.filter(action_type="update_user_self").count()
    auth_client.patch(
        reverse("identity:me"),
        {"display_name": "Audited"},
        format="json",
    )
    post = AuditLog.objects.filter(action_type="update_user_self").count()
    assert post == pre + 1


@pytest.mark.django_db
def test_patch_me_unauthenticated_returns_401_or_403(client):
    resp = client.patch(
        reverse("identity:me"),
        {"display_name": "x"},
        format="json",
    )
    assert resp.status_code in (
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    )


# ---------------------------------------------------------------------------
# PATCH /api/me/person/
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_patch_me_person_updates_given_names(auth_client, user):
    resp = auth_client.patch(
        reverse("identity:me-person"),
        {"given_names": "Different"},
        format="json",
    )
    assert resp.status_code == status.HTTP_200_OK
    user.person.refresh_from_db()
    assert user.person.given_names == "Different"


@pytest.mark.django_db
def test_patch_me_person_updates_birth_date(auth_client, user):
    resp = auth_client.patch(
        reverse("identity:me-person"),
        {"birth_date": "1990-05-12", "birth_date_precision": "exact"},
        format="json",
    )
    assert resp.status_code == status.HTTP_200_OK
    user.person.refresh_from_db()
    assert user.person.birth_date == datetime.date(1990, 5, 12)
    assert user.person.birth_date_precision == "exact"


@pytest.mark.django_db
def test_patch_me_person_updates_short_bio(auth_client, user):
    resp = auth_client.patch(
        reverse("identity:me-person"),
        {"short_bio": "Curioso, padre, sviluppatore."},
        format="json",
    )
    assert resp.status_code == status.HTTP_200_OK
    user.person.refresh_from_db()
    assert user.person.short_bio == "Curioso, padre, sviluppatore."


@pytest.mark.django_db
def test_patch_me_person_cannot_change_is_living(auth_client, user):
    auth_client.patch(
        reverse("identity:me-person"),
        {"is_living": False, "given_names": "X"},
        format="json",
    )
    user.person.refresh_from_db()
    assert user.person.is_living is True


@pytest.mark.django_db
def test_patch_me_person_cannot_change_death_date(auth_client, user):
    auth_client.patch(
        reverse("identity:me-person"),
        {"death_date": "2020-01-01", "given_names": "X"},
        format="json",
    )
    user.person.refresh_from_db()
    assert user.person.death_date is None


@pytest.mark.django_db
def test_patch_me_person_creates_audit_log_entry(auth_client):
    pre = AuditLog.objects.filter(action_type="update_person_self").count()
    auth_client.patch(
        reverse("identity:me-person"),
        {"short_bio": "Audited bio"},
        format="json",
    )
    post = AuditLog.objects.filter(action_type="update_person_self").count()
    assert post == pre + 1


@pytest.mark.django_db
def test_patch_me_person_unauthenticated_returns_401_or_403(client):
    resp = client.patch(
        reverse("identity:me-person"),
        {"given_names": "x"},
        format="json",
    )
    assert resp.status_code in (
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    )


@pytest.mark.django_db
def test_patch_me_person_user_without_person_returns_404(client, user):
    user.person = None
    user.save(update_fields=["person", "updated_at"])
    token = Token.objects.create(user=user)
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    resp = client.patch(
        reverse("identity:me-person"),
        {"given_names": "x"},
        format="json",
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# POST /api/me/change-password/
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_change_password_with_correct_current_password_succeeds(auth_client, user):
    resp = auth_client.post(
        reverse("identity:change-password"),
        {
            "current_password": "strongpass123",
            "new_password": "brandnewpass456",
        },
        format="json",
    )
    assert resp.status_code == status.HTTP_200_OK
    user.refresh_from_db()
    assert user.check_password("brandnewpass456")


@pytest.mark.django_db
def test_change_password_with_wrong_current_password_returns_400(auth_client):
    resp = auth_client.post(
        reverse("identity:change-password"),
        {
            "current_password": "wrongpass",
            "new_password": "brandnewpass456",
        },
        format="json",
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_change_password_too_short_returns_400(auth_client):
    resp = auth_client.post(
        reverse("identity:change-password"),
        {
            "current_password": "strongpass123",
            "new_password": "short",
        },
        format="json",
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_change_password_same_as_current_returns_400(auth_client):
    resp = auth_client.post(
        reverse("identity:change-password"),
        {
            "current_password": "strongpass123",
            "new_password": "strongpass123",
        },
        format="json",
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_change_password_does_not_logout_current_session(auth_client, user):
    current_key = auth_client._token.key
    auth_client.post(
        reverse("identity:change-password"),
        {
            "current_password": "strongpass123",
            "new_password": "brandnewpass456",
        },
        format="json",
    )
    # Current token still exists.
    assert Token.objects.filter(user=user, key=current_key).exists()
    # And the session still works.
    resp = auth_client.get(reverse("identity:me"))
    assert resp.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_change_password_preserves_current_token(auth_client, user):
    """DRF Token is OneToOneField — current token is preserved during change_password."""
    current_token_key = Token.objects.get(user=user).key
    resp = auth_client.post(
        reverse("identity:change-password"),
        {
            "current_password": "strongpass123",
            "new_password": "brandnewpass456",
        },
        format="json",
    )
    assert resp.status_code == status.HTTP_200_OK
    assert Token.objects.filter(user=user, key=current_token_key).exists()


@pytest.mark.django_db
def test_change_password_creates_audit_log_entry(auth_client):
    pre = AuditLog.objects.filter(action_type="change_password").count()
    auth_client.post(
        reverse("identity:change-password"),
        {
            "current_password": "strongpass123",
            "new_password": "brandnewpass456",
        },
        format="json",
    )
    post = AuditLog.objects.filter(action_type="change_password").count()
    assert post == pre + 1


@pytest.mark.django_db
def test_change_password_unauthenticated_returns_401_or_403(client):
    resp = client.post(
        reverse("identity:change-password"),
        {
            "current_password": "strongpass123",
            "new_password": "brandnewpass456",
        },
        format="json",
    )
    assert resp.status_code in (
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    )
