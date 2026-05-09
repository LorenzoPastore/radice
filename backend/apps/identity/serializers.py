"""DRF serializers for identity endpoints."""
from django.core.validators import MinLengthValidator
from rest_framework import serializers

from .models import Person, User


class RegistrationSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(
        write_only=True, validators=[MinLengthValidator(8)]
    )
    given_names = serializers.CharField(max_length=200)
    surname = serializers.CharField(max_length=200)
    display_name = serializers.CharField(
        max_length=200, required=False, allow_blank=True
    )
    locale = serializers.CharField(max_length=10, required=False, default="it-IT")

    def validate_password(self, value):
        # Minimal weak-password block. Extend with django.contrib.auth.password_validation.
        if value.lower() in ("password", "12345678", "qwerty123"):
            raise serializers.ValidationError("Password troppo debole")
        return value


class EmailVerificationSerializer(serializers.Serializer):
    token = serializers.CharField()


class UserPublicSerializer(serializers.ModelSerializer):
    """Public-facing User payload (no sensitive fields)."""

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "display_name",
            "email_verified_at",
            "locale",
            "timezone",
            "created_at",
        )
        read_only_fields = fields


class PersonPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Person
        fields = (
            "id",
            "given_names",
            "surname",
            "surname_at_birth",
            "nicknames",
            "is_living",
            "birth_date",
            "birth_date_precision",
            "death_date",
            "death_date_precision",
            "gender",
            "short_bio",
            "is_claimed",
            "created_at",
        )
        read_only_fields = fields


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, min_length=8)


class MeUserSerializer(serializers.ModelSerializer):
    """Full self-view of the current User (no sensitive token fields)."""

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "display_name",
            "email_verified_at",
            "locale",
            "timezone",
            "privacy_preset",
            "notification_preferences",
            "created_at",
        )
        read_only_fields = (
            "id",
            "email",
            "email_verified_at",
            "created_at",
        )


class MeUserUpdateSerializer(serializers.Serializer):
    display_name = serializers.CharField(max_length=200, required=False)
    locale = serializers.CharField(max_length=10, required=False)
    timezone = serializers.CharField(max_length=50, required=False)
    privacy_preset = serializers.ChoiceField(
        choices=[(c.value, c.label) for c in User.PrivacyPreset],
        required=False,
    )
    notification_preferences = serializers.JSONField(required=False)


class MePersonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Person
        fields = (
            "id",
            "given_names",
            "surname",
            "surname_at_birth",
            "nicknames",
            "is_living",
            "birth_date",
            "birth_date_precision",
            "birth_place",
            "death_date",
            "death_date_precision",
            "death_place",
            "gender",
            "short_bio",
            "is_claimed",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "is_living",
            "death_date",
            "death_date_precision",
            "death_place",
            "is_claimed",
            "created_at",
            "updated_at",
        )


class MePersonUpdateSerializer(serializers.Serializer):
    given_names = serializers.CharField(max_length=200, required=False)
    surname = serializers.CharField(max_length=200, required=False)
    surname_at_birth = serializers.CharField(
        max_length=200, required=False, allow_null=True, allow_blank=True
    )
    nicknames = serializers.ListField(
        child=serializers.CharField(max_length=100), required=False
    )
    birth_date = serializers.DateField(required=False, allow_null=True)
    birth_date_precision = serializers.ChoiceField(
        choices=[(c.value, c.label) for c in Person.DatePrecision],
        required=False,
    )
    birth_place = serializers.CharField(
        max_length=255, required=False, allow_null=True, allow_blank=True
    )
    gender = serializers.ChoiceField(
        choices=[(c.value, c.label) for c in Person.Gender],
        required=False,
    )
    short_bio = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)
