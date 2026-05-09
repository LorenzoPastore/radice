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
    path("auth/login/", views.login_view, name="login"),
    path("auth/logout/", views.logout_view, name="logout"),
    path(
        "auth/password-reset/request/",
        views.password_reset_request_view,
        name="password-reset-request",
    ),
    path(
        "auth/password-reset/confirm/",
        views.password_reset_confirm_view,
        name="password-reset-confirm",
    ),
    path("me/", views.me_view, name="me"),
    path("me/person/", views.me_person_view, name="me-person"),
    path(
        "me/change-password/",
        views.change_password_view,
        name="change-password",
    ),
]
