"""Root URL configuration for Radice."""

from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    # Admin
    path("admin/", admin.site.urls),

    # Health check (from core app)
    path("api/", include("apps.core.urls")),

    # Identity (auth, registration, email verification)
    path("api/", include("apps.identity.urls")),

    # OpenAPI schema + Swagger UI
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),

    # Domain apps will register their URL prefixes here, e.g.:
    # path("api/identity/", include("apps.identity.urls")),
    # path("api/tree/", include("apps.tree.urls")),
]
