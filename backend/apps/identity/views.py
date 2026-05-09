"""Identity API views: register, verify-email, resend-verification."""
import logging

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from .serializers import (
    EmailVerificationSerializer,
    PersonPublicSerializer,
    RegistrationSerializer,
    UserPublicSerializer,
)
from .services.email_verification_service import (
    VerificationError,
    send_verification_email,
    verify_email,
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
