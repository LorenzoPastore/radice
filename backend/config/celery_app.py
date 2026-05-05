"""Celery application for Radice."""

import os

from celery import Celery

# Default to production settings; override with DJANGO_SETTINGS_MODULE env var.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

app = Celery("radice")

# Use Django settings prefixed with CELERY_ for all Celery config.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks in all INSTALLED_APPS.
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):  # type: ignore[no-untyped-def]
    """Introspection task for development/debugging."""
    print(f"Request: {self.request!r}")  # noqa: T201
