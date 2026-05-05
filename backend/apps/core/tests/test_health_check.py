"""Tests for the /api/health/ endpoint."""

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from unittest.mock import patch


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.mark.django_db
class TestHealthCheck:
    """Tests for GET /api/health/."""

    url = "/api/health/"

    def test_returns_200_when_all_healthy(self, client: APIClient) -> None:
        response = client.get(self.url)
        assert response.status_code == status.HTTP_200_OK

    def test_response_has_required_keys(self, client: APIClient) -> None:
        response = client.get(self.url)
        data = response.json()
        assert "status" in data
        assert "db" in data
        assert "redis" in data

    def test_status_ok_when_all_healthy(self, client: APIClient) -> None:
        response = client.get(self.url)
        data = response.json()
        assert data["status"] == "ok"
        assert data["db"] == "ok"

    def test_accessible_without_authentication(self, client: APIClient) -> None:
        """Health endpoint must be reachable by load balancers without auth."""
        response = client.get(self.url)
        assert response.status_code != status.HTTP_401_UNAUTHORIZED
        assert response.status_code != status.HTTP_403_FORBIDDEN

    def test_only_get_method_allowed(self, client: APIClient) -> None:
        for method in ("post", "put", "patch", "delete"):
            response = getattr(client, method)(self.url)
            assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_returns_503_when_db_is_down(self, client: APIClient) -> None:
        with patch("apps.core.views._check_db", return_value="error"):
            response = client.get(self.url)
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        data = response.json()
        assert data["status"] == "degraded"
        assert data["db"] == "error"

    def test_returns_503_when_redis_is_down(self, client: APIClient) -> None:
        with patch("apps.core.views._check_redis", return_value="error"):
            response = client.get(self.url)
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        data = response.json()
        assert data["status"] == "degraded"
        assert data["redis"] == "error"

    def test_returns_503_when_both_down(self, client: APIClient) -> None:
        with (
            patch("apps.core.views._check_db", return_value="error"),
            patch("apps.core.views._check_redis", return_value="error"),
        ):
            response = client.get(self.url)
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        data = response.json()
        assert data["status"] == "degraded"
        assert data["db"] == "error"
        assert data["redis"] == "error"

    def test_db_check_handles_exception_gracefully(self, client: APIClient) -> None:
        """DB check must catch exceptions, not propagate a 500."""
        with patch(
            "apps.core.views.connection.cursor", side_effect=Exception("DB unreachable")
        ):
            response = client.get(self.url)
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.json()["db"] == "error"
