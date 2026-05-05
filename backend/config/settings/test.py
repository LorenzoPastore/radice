"""Test settings — fast, hermetic, no external services."""

from .base import *  # noqa: F401, F403
from .base import env

# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
DEBUG = False
SECRET_KEY = "django-insecure-test-secret-key-not-for-production"
ALLOWED_HOSTS = ["*"]

# Disable Sentry in tests
SENTRY_DSN = ""

# ---------------------------------------------------------------------------
# Database — SQLite in memory for speed
# ---------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# ---------------------------------------------------------------------------
# Cache — in-memory dummy cache (no Redis dependency)
# ---------------------------------------------------------------------------
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# ---------------------------------------------------------------------------
# Celery — run tasks synchronously in tests
# ---------------------------------------------------------------------------
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# ---------------------------------------------------------------------------
# Email — suppress all outbound email
# ---------------------------------------------------------------------------
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# ---------------------------------------------------------------------------
# Passwords — use fast hasher
# ---------------------------------------------------------------------------
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# ---------------------------------------------------------------------------
# Media / static
# ---------------------------------------------------------------------------
MEDIA_ROOT = "/tmp/radice_test_media"  # noqa: S108

# ---------------------------------------------------------------------------
# django-allauth — skip email verification in tests
# ---------------------------------------------------------------------------
ACCOUNT_EMAIL_VERIFICATION = "none"
