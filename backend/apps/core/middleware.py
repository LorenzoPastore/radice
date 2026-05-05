"""Core middleware for Radice."""

import threading
from collections.abc import Callable
from typing import Any

from django.http import HttpRequest, HttpResponse

# Thread-local storage for audit context — allows signal handlers and model
# methods to access the current request user without being passed it explicitly.
_audit_local = threading.local()


def get_audit_user() -> Any:
    """Return the user stored by AuditContextMiddleware, or None."""
    return getattr(_audit_local, "user", None)


class AuditContextMiddleware:
    """
    Store the authenticated user (or None) in a thread-local so that audit log
    signal handlers can access it without needing the request object.

    Usage in a signal handler::

        from apps.core.middleware import get_audit_user
        actor = get_audit_user()
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Populate before the view runs
        user = getattr(request, "user", None)
        _audit_local.user = user if (user and user.is_authenticated) else None

        response = self.get_response(request)

        # Clean up to avoid leaking state across requests in long-lived threads
        _audit_local.user = None

        return response


class RequestCacheMiddleware:
    """
    Attach a plain dict to each request at ``request.cache``.

    Use it to memoise expensive per-request computations (e.g. permission
    checks that hit the DB) so the same query is not repeated within a single
    request/response cycle.

    Example::

        def get_family(request, family_id):
            key = f"family:{family_id}"
            if key not in request.cache:
                request.cache[key] = Family.objects.get(pk=family_id)
            return request.cache[key]
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request.cache: dict[str, Any] = {}  # type: ignore[attr-defined]
        return self.get_response(request)
