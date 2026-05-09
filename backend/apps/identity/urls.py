"""Identity URL routing."""
from django.urls import path

from . import views

app_name = "identity"

urlpatterns = [
    path("auth/register/", views.register_view, name="register"),
    path("auth/verify-email/", views.verify_email_view, name="verify-email"),
    path(
        "auth/resend-verification/",
        views.resend_verification_view,
        name="resend-verification",
    ),
]
