"""Governance domain models.

For Milestone 1 only `AuditLog` is implemented. Merge models arrive later.

`AuditLog` is append-only:
- Model layer: `save()` of an existing pk and `delete()` raise PermissionDenied.
- DB layer: PostgreSQL trigger blocks UPDATE/DELETE
  (see migration 0002_audit_log_append_only).
"""

import uuid

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import models


class AuditLog(models.Model):
    """Append-only audit log entry. Vedi apps/governance/CLAUDE.md vincolo 1."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_actions",
    )
    action_type = models.CharField(max_length=80)
    entity_type = models.CharField(max_length=80)
    entity_id = models.UUIDField()
    changes_diff = models.JSONField(null=True, blank=True)
    context = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "governance_audit_log"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["entity_type", "entity_id"]),
            models.Index(fields=["actor_user", "-created_at"]),
            models.Index(fields=["action_type", "-created_at"]),
        ]

    def save(self, *args, **kwargs):
        # Block UPDATE at the model layer. DB trigger is the authoritative guard.
        if self.pk and AuditLog.objects.filter(pk=self.pk).exists():
            raise PermissionDenied(
                "AuditLog is append-only — UPDATE not permitted"
            )
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionDenied(
            "AuditLog is append-only — DELETE not permitted"
        )

    def __str__(self):
        return (
            f"{self.action_type} on {self.entity_type}#{self.entity_id} "
            f"by {self.actor_user_id}"
        )
