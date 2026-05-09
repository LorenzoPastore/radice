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
