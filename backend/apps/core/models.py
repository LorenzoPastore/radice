"""Core abstract base models shared across all Radice apps."""

from django.db import models


class BaseModel(models.Model):
    """
    Abstract base model providing standard audit fields for all Radice models.

    All domain models should inherit from this rather than models.Model directly.
    Soft-delete is supported: use `soft_delete()` instead of `delete()` when you
    want to retain data for audit / family-history purposes.
    """

    id = models.BigAutoField(primary_key=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]

    def soft_delete(self) -> None:
        """
        Mark the record as deleted without removing it from the database.

        Sets `is_deleted=True` and `deleted_at` to the current timestamp.
        Domain logic (e.g. cascading soft-deletes to children) should be
        implemented in the concrete model's `soft_delete` override.
        """
        from django.utils import timezone

        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=["is_deleted", "deleted_at", "updated_at"])

    def restore(self) -> None:
        """Undo a soft-delete."""
        self.is_deleted = False
        self.deleted_at = None
        self.save(update_fields=["is_deleted", "deleted_at", "updated_at"])
