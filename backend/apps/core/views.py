"""Core views — infrastructure endpoints."""

import logging

from django.db import connection
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

logger = logging.getLogger(__name__)


def _check_db() -> str:
    """Return 'ok' if the default DB answers SELECT 1, else 'error'."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return "ok"
    except Exception:
        logger.exception("Health check: DB error")
        return "error"


def _check_redis() -> str:
    """Return 'ok' if Redis answers PING, else 'error'."""
    try:
        from django.core.cache import cache

        cache.set("_health", "1", timeout=5)
        result = cache.get("_health")
        return "ok" if result == "1" else "error"
    except Exception:
        logger.exception("Health check: Redis error")
        return "error"


@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request: Request) -> Response:
    """
    GET /api/health/

    Returns the operational status of the service and its dependencies.

    Response body::

        {
            "status": "ok" | "degraded",
            "db":     "ok" | "error",
            "redis":  "ok" | "error"
        }

    HTTP 200 when everything is healthy, HTTP 503 when any component fails.
    """
    db_status = _check_db()
    redis_status = _check_redis()

    all_ok = db_status == "ok" and redis_status == "ok"
    overall = "ok" if all_ok else "degraded"
    http_status = 200 if all_ok else 503

    return Response(
        {
            "status": overall,
            "db": db_status,
            "redis": redis_status,
        },
        status=http_status,
    )
