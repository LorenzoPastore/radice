"""Factory-boy factories for governance models."""

import factory
from factory.django import DjangoModelFactory

from .models import AuditLog


class AuditLogFactory(DjangoModelFactory):
    class Meta:
        model = AuditLog

    action_type = "test_action"
    entity_type = "test_entity"
    entity_id = factory.Faker("uuid4")
