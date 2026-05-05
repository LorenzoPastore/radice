"""Local development settings."""

from .base import *  # noqa: F401, F403
from .base import INSTALLED_APPS, LOGGING, env

# ---------------------------------------------------------------------------
# Core overrides
# ---------------------------------------------------------------------------
DEBUG = True
ALLOWED_HOSTS = ["*"]

# Disable Sentry in local development
SENTRY_DSN = ""

# ---------------------------------------------------------------------------
# Extra apps for development
# ---------------------------------------------------------------------------
INSTALLED_APPS = INSTALLED_APPS + [
    "django_extensions",
]

# ---------------------------------------------------------------------------
# Database — allow DATABASE_URL override, fall back to local postgres
# ---------------------------------------------------------------------------
# (inherited from base, DATABASE_URL read from .env)

# ---------------------------------------------------------------------------
# Email — print to console
# ---------------------------------------------------------------------------
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# ---------------------------------------------------------------------------
# CORS — allow everything locally
# ---------------------------------------------------------------------------
CORS_ALLOW_ALL_ORIGINS = True

# ---------------------------------------------------------------------------
# Logging — more verbose in dev
# ---------------------------------------------------------------------------
LOGGING["loggers"]["apps"]["level"] = "DEBUG"  # type: ignore[index]
LOGGING["root"]["level"] = "DEBUG"  # type: ignore[index]
