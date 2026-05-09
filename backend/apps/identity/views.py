"""Identity API views: register, verify-email, resend-verification."""
import logging

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from .serializers import (
    ChangePasswordSerializer,
    EmailVerificationSerializer,
    LoginSerializer,
    MePersonSerializer,
    MePersonUpdateSerializer,
    MeUserSerializer,
    MeUserUpdateSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    PersonPublicSerializer,
    RegistrationSerializer,
    UserPublicSerializer,
)
from .services.auth_service import AuthError, login_user, logout_user
from .services.me_service import (
    change_password,
    update_me_person,
    update_me_user,
)
from .services.email_verification_service import (
    VerificationError,
    send_verification_email,
    verify_email,
)
from .services.password_reset_service import (
    PasswordResetError,
    confirm_password_reset,
    request_password_reset,
)
from .services.registration_service import RegistrationError, register_new_user

logger = logging.getLogger(__name__)


@api_view(["POST"])
@permission_classes([AllowAny])
def register_view(request: Request) -> Response:
    """POST /api/auth/register/ — Register a new user."""
    serializer = RegistrationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    try:
        user, person = register_new_user(
            email=data["email"],
            password=data["password"],
            given_names=data["given_names"],
            surname=data["surname"],
            display_name=data.get("display_name") or None,
            locale=data.get("locale", "it-IT"),
        )
    except RegistrationError as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    # Fire-and-forget email — failure does not abort registration.
    try:
        send_verification_email(user)
    except Exception:
        logger.exception("Failed to send verification email")

    return Response(
        {
            "user": UserPublicSerializer(user).data,
            "person": PersonPublicSerializer(person).data,
            "detail": "Registrazione completata. Controlla la tua email per verificare l'account.",
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def verify_email_view(request: Request) -> Response:
    """POST /api/auth/verify-email/ — Verify email address with token."""
    serializer = EmailVerificationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    try:
        user = verify_email(token=serializer.validated_data["token"])
    except VerificationError as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    return Response(
        {
            "user": UserPublicSerializer(user).data,
            "detail": "Email verificata con successo.",
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def resend_verification_view(request: Request) -> Response:
    """POST /api/auth/resend-verification/ — Resend verification email."""
    user = request.user
    if user.email_verified_at is not None:
        return Response(
            {"detail": "Email già verificata."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    send_verification_email(user)
    return Response({"detail": "Email di verifica inviata."})


@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request: Request) -> Response:
    """POST /api/auth/login/ — Authenticate and obtain a token."""
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    try:
        user, token = login_user(
            email=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
        )
    except AuthError as e:
        return Response(
            {"detail": str(e)}, status=status.HTTP_401_UNAUTHORIZED
        )

    return Response(
        {
            "token": token,
            "user": UserPublicSerializer(user).data,
            "email_verified": user.email_verified_at is not None,
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_view(request: Request) -> Response:
    """POST /api/auth/logout/ — Revoke current token."""
    logout_user(user=request.user)
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["POST"])
@permission_classes([AllowAny])
def password_reset_request_view(request: Request) -> Response:
    """POST /api/auth/password-reset/request/ — Send reset email."""
    serializer = PasswordResetRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    request_password_reset(email=serializer.validated_data["email"])
    # Always return 200 — never leak whether email is registered
    return Response(
        {"detail": "Se l'email è registrata, riceverai un link di reset."}
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def password_reset_confirm_view(request: Request) -> Response:
    """POST /api/auth/password-reset/confirm/ — Set new password using token."""
    serializer = PasswordResetConfirmSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    try:
        confirm_password_reset(
            token=serializer.validated_data["token"],
            new_password=serializer.validated_data["new_password"],
        )
    except PasswordResetError as e:
        return Response(
            {"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST
        )

    return Response({"detail": "Password aggiornata. Effettua il login."})


# ---------------------------------------------------------------------------
# /api/me/ — current user's own data
# ---------------------------------------------------------------------------
@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def me_view(request: Request) -> Response:
    """GET/PATCH /api/me/ — Current user (User-level fields).

    GET returns the current User and its associated Person.
    PATCH updates whitelisted User-level fields only.
    """
    if request.method == "GET":
        person = request.user.person
        return Response(
            {
                "user": MeUserSerializer(request.user).data,
                "person": MePersonSerializer(person).data if person else None,
            }
        )

    # PATCH
    serializer = MeUserUpdateSerializer(data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    user = update_me_user(user=request.user, changes=serializer.validated_data)
    person = user.person
    return Response(
        {
            "user": MeUserSerializer(user).data,
            "person": MePersonSerializer(person).data if person else None,
        }
    )


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def me_person_view(request: Request) -> Response:
    """PATCH /api/me/person/ — Edit own Person fields."""
    if request.user.person is None:
        return Response(
            {"detail": "Profilo Person non disponibile"},
            status=status.HTTP_404_NOT_FOUND,
        )

    serializer = MePersonUpdateSerializer(data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    person = update_me_person(
        user=request.user, changes=serializer.validated_data
    )
    return Response(MePersonSerializer(person).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def change_password_view(request: Request) -> Response:
    """POST /api/me/change-password/ — Change own password.

    Requires the current password. Revokes all OTHER auth tokens but
    preserves the current session's token so the user remains logged in.
    """
    serializer = ChangePasswordSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    # Preserve the current session token (request.auth is the Token instance
    # under TokenAuthentication).
    current_token_key = None
    auth = request.auth
    if auth is not None and hasattr(auth, "key"):
        current_token_key = auth.key

    try:
        change_password(
            user=request.user,
            current_password=serializer.validated_data["current_password"],
            new_password=serializer.validated_data["new_password"],
            current_token_key=current_token_key,
        )
    except ValueError as e:
        return Response(
            {"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST
        )

    return Response({"detail": "Password aggiornata."})
