"""Tests sull'append-only di AuditLog (model layer + DB trigger)."""

import uuid

import pytest
from django.core.exceptions import PermissionDenied
from django.db import connection

from apps.governance.factories import AuditLogFactory
from apps.governance.models import AuditLog


@pytest.mark.django_db(transaction=True)
class TestAuditLogAppendOnly:
    def test_can_insert(self):
        log = AuditLogFactory()
        assert log.pk is not None

    def test_save_existing_raises_permission_denied(self):
        log = AuditLogFactory()
        log.action_type = "modified"
        with pytest.raises(PermissionDenied):
            log.save()

    def test_delete_raises_permission_denied(self):
        log = AuditLogFactory()
        with pytest.raises(PermissionDenied):
            log.delete()

    def test_db_trigger_blocks_raw_update(self):
        log = AuditLogFactory()
        with pytest.raises(Exception) as exc_info:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE governance_audit_log "
                    "SET action_type = 'hacked' WHERE id = %s",
                    [str(log.id)],
                )
        msg = str(exc_info.value).lower()
        assert "append-only" in msg or "is not permitted" in msg

    def test_db_trigger_blocks_raw_delete(self):
        log = AuditLogFactory()
        with pytest.raises(Exception) as exc_info:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM governance_audit_log WHERE id = %s",
                    [str(log.id)],
                )
        msg = str(exc_info.value).lower()
        assert "append-only" in msg or "is not permitted" in msg

    def test_db_allows_raw_insert(self):
        entity_id = uuid.uuid4()
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO governance_audit_log "
                "(id, actor_user_id, action_type, entity_type, entity_id, "
                "changes_diff, context, created_at) "
                "VALUES (%s, NULL, 'manual', 'test', %s, NULL, '{}', NOW())",
                [str(uuid.uuid4()), str(entity_id)],
            )
        assert AuditLog.objects.filter(entity_id=entity_id).exists()
