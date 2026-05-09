"""Audit log service — single entry point for writing to governance_audit_log."""
import json
from typing import Any, Optional

from django.core.serializers.json import DjangoJSONEncoder
from django.db import models

from apps.governance.models import AuditLog


def _normalize_for_json(value: Any) -> Any:
    """Roundtrip through DjangoJSONEncoder so date/datetime/UUID/Decimal etc.
    are converted to JSON-safe types before being stored in JSONB."""
    if value is None:
        return None
    return json.loads(json.dumps(value, cls=DjangoJSONEncoder))


def write_audit(
    *,
    action_type: str,
    entity: models.Model,
    actor=None,
    changes_diff: Optional[dict[str, Any]] = None,
    context: Optional[dict[str, Any]] = None,
) -> AuditLog:
    """
    Write an immutable entry to the audit log.

    Args:
        action_type: Short identifier (e.g. 'create_person', 'update_person')
        entity: The Django model instance affected
        actor: User performing the action (None for system actions)
        changes_diff: Dict with 'before' and 'after' keys for updates
        context: Optional metadata (IP, session_id, etc.)

    Returns:
        The created AuditLog entry.
    """
    return AuditLog.objects.create(
        actor_user=actor,
        action_type=action_type,
        entity_type=entity._meta.db_table,
        entity_id=entity.pk,
        changes_diff=_normalize_for_json(changes_diff),
        context=_normalize_for_json(context) if context else {},
    )
