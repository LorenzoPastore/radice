"""Tests for the audit_service.write_audit helper."""
import pytest

from apps.governance.models import AuditLog
from apps.governance.services.audit_service import write_audit
from apps.identity.models import Person, User


@pytest.fixture
def user(db):
    return User.objects.create_user(
        email="actor@example.com",
        password="testpass123",
        display_name="Actor",
    )


@pytest.fixture
def person(db, user):
    return Person.objects.create(
        given_names="Mario",
        surname="Rossi",
        is_living=True,
        created_by_user=user,
    )


@pytest.mark.django_db
def test_write_audit_creates_entry(user, person):
    entry = write_audit(action_type="create_person", entity=person, actor=user)
    assert AuditLog.objects.filter(pk=entry.pk).exists()
    assert entry.action_type == "create_person"
    assert entry.entity_id == person.pk


@pytest.mark.django_db
def test_write_audit_with_actor(user, person):
    entry = write_audit(action_type="update_person", entity=person, actor=user)
    assert entry.actor_user_id == user.pk


@pytest.mark.django_db
def test_write_audit_without_actor_is_system_action(person):
    entry = write_audit(action_type="system_action", entity=person, actor=None)
    assert entry.actor_user is None


@pytest.mark.django_db
def test_write_audit_includes_changes_diff(user, person):
    diff = {"before": {"surname": "Rossi"}, "after": {"surname": "Bianchi"}}
    entry = write_audit(
        action_type="update_person",
        entity=person,
        actor=user,
        changes_diff=diff,
    )
    entry.refresh_from_db()
    assert entry.changes_diff == diff


@pytest.mark.django_db
def test_write_audit_default_context_is_empty_dict(user, person):
    entry = write_audit(action_type="x", entity=person, actor=user)
    assert entry.context == {}


@pytest.mark.django_db
def test_write_audit_entity_type_matches_db_table(user, person):
    entry = write_audit(action_type="x", entity=person, actor=user)
    assert entry.entity_type == person._meta.db_table
    assert entry.entity_type == "identity_persons"
