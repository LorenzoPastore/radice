"""Service-level tests for me_service."""
import pytest
from rest_framework.authtoken.models import Token

from apps.governance.models import AuditLog
from apps.identity.services.me_service import (
    change_password,
    update_me_person,
    update_me_user,
)
from apps.identity.services.registration_service import register_new_user


@pytest.fixture
def user(db):
    u, _ = register_new_user(
        email="svc@example.com",
        password="strongpass123",
        given_names="Svc",
        surname="User",
    )
    return u


# ---------------------------------------------------------------------------
# update_me_user
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_update_me_user_only_whitelist_fields(user):
    original_email = user.email
    update_me_user(
        user=user,
        changes={
            "display_name": "OK",
            "email": "hacker@evil.com",  # NOT whitelisted
            "is_staff": True,            # NOT whitelisted
        },
    )
    user.refresh_from_db()
    assert user.display_name == "OK"
    assert user.email == original_email
    assert user.is_staff is False


@pytest.mark.django_db
def test_update_me_user_writes_audit_with_diff(user):
    pre = AuditLog.objects.filter(action_type="update_user_self").count()
    update_me_user(user=user, changes={"display_name": "Differente"})
    post_qs = AuditLog.objects.filter(action_type="update_user_self")
    assert post_qs.count() == pre + 1
    entry = post_qs.latest("created_at")
    assert entry.changes_diff is not None
    assert "before" in entry.changes_diff
    assert "after" in entry.changes_diff
    assert entry.changes_diff["after"]["display_name"] == "Differente"


@pytest.mark.django_db
def test_update_me_user_no_changes_no_audit(user):
    pre = AuditLog.objects.filter(action_type="update_user_self").count()
    # No whitelisted fields → no audit, no save.
    update_me_user(user=user, changes={"email": "x@y.z", "is_staff": True})
    post = AuditLog.objects.filter(action_type="update_user_self").count()
    assert post == pre


# ---------------------------------------------------------------------------
# update_me_person
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_update_me_person_only_whitelist_fields(user):
    update_me_person(
        user=user,
        changes={
            "given_names": "Aldo",
            "is_living": False,        # NOT whitelisted
            "is_claimed": True,        # NOT whitelisted
            "death_date": "2020-01-01",  # NOT whitelisted
        },
    )
    user.person.refresh_from_db()
    assert user.person.given_names == "Aldo"
    assert user.person.is_living is True
    assert user.person.is_claimed is False
    assert user.person.death_date is None


@pytest.mark.django_db
def test_update_me_person_writes_audit_with_diff(user):
    pre = AuditLog.objects.filter(action_type="update_person_self").count()
    update_me_person(user=user, changes={"short_bio": "Una bio"})
    post_qs = AuditLog.objects.filter(action_type="update_person_self")
    assert post_qs.count() == pre + 1
    entry = post_qs.latest("created_at")
    assert entry.changes_diff["after"]["short_bio"] == "Una bio"
    assert "short_bio" in entry.changes_diff["before"]


@pytest.mark.django_db
def test_update_me_person_user_without_person_raises(user):
    user.person = None
    user.save(update_fields=["person", "updated_at"])
    with pytest.raises(ValueError):
        update_me_person(user=user, changes={"given_names": "X"})


# ---------------------------------------------------------------------------
# change_password
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_change_password_keeps_current_token(user):
    """DRF stock Token is OneToOneField — only one token per user.
    If current_token_key matches, the user's token is preserved."""
    current = Token.objects.create(user=user)
    change_password(
        user=user,
        current_password="strongpass123",
        new_password="brandnewpass456",
        current_token_key=current.key,
    )
    assert Token.objects.filter(key=current.key).exists()


@pytest.mark.django_db
def test_change_password_revokes_token_if_no_current_token(user):
    """If no current_token_key passed, the user's token is deleted."""
    Token.objects.create(user=user)
    change_password(
        user=user,
        current_password="strongpass123",
        new_password="brandnewpass456",
        current_token_key=None,
    )
    assert Token.objects.filter(user=user).count() == 0


@pytest.mark.django_db
def test_change_password_revokes_token_if_current_token_does_not_match(user):
    """If current_token_key doesn't match any existing, all are deleted."""
    Token.objects.create(user=user)
    change_password(
        user=user,
        current_password="strongpass123",
        new_password="brandnewpass456",
        current_token_key="some-stale-key-not-in-db",
    )
    assert Token.objects.filter(user=user).count() == 0
