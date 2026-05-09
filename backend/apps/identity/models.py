"""Identity domain models: User, Person, PersonClaim, Invitation.

Implements the foundational User <-> Person separation (ADR-005).

Note on the User <-> Person relation:
The data-model.md spec describes the relation from both sides
(`users.person_id` UNIQUE NOT NULL and `persons.user_id` UNIQUE NULL).
In the ORM a single OneToOneField creates the inverse automatically,
so we model the link ONCE on `User.person` (related_name='user_account').
A Person therefore reads its associated User via `person.user_account`.
This is functionally equivalent to the spec.

User.person is declared nullable here for the chicken-and-egg of initial
migrations; the registration service is responsible for enforcing the
NOT NULL invariant at the application layer (see CLAUDE.md vincolo 2).
"""

import uuid

from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models import F, Q
from django.utils.translation import gettext_lazy as _


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------
class UserManager(BaseUserManager):
    """Manager for the custom email-based User model."""

    use_in_migrations = True

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        extra_fields.setdefault("display_name", email.split("@")[0])
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self.create_user(email, password, **extra_fields)


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------
class User(AbstractBaseUser, PermissionsMixin):
    """Account utente. Vedi apps/identity/CLAUDE.md."""

    class PrivacyPreset(models.TextChoices):
        RESERVED = "reserved", _("Reserved")
        BALANCED = "balanced", _("Balanced")
        OPEN = "open", _("Open")
        CUSTOM = "custom", _("Custom")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    # `password` field is provided by AbstractBaseUser
    oauth_providers = models.JSONField(default=list, blank=True)
    person = models.OneToOneField(
        "identity.Person",
        on_delete=models.PROTECT,
        related_name="user_account",
        null=True,
        blank=True,  # nullable solo per init migration; service enforce NOT NULL
    )
    display_name = models.CharField(max_length=200)
    locale = models.CharField(max_length=10, default="it-IT")
    timezone = models.CharField(max_length=50, default="Europe/Rome")
    notification_preferences = models.JSONField(default=dict, blank=True)
    privacy_preset = models.CharField(
        max_length=20,
        choices=PrivacyPreset.choices,
        default=PrivacyPreset.BALANCED,
    )
    privacy_custom_overrides = models.JSONField(null=True, blank=True)
    last_login_at = models.DateTimeField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["display_name"]

    class Meta:
        db_table = "identity_users"
        verbose_name = "user"
        verbose_name_plural = "users"
        indexes = [
            models.Index(fields=["deleted_at"]),
            models.Index(fields=["email_verified_at"]),
        ]

    def __str__(self):
        return f"{self.display_name} <{self.email}>"


# ---------------------------------------------------------------------------
# Person
# ---------------------------------------------------------------------------
class Person(models.Model):
    """Persona reale (viva o morta). Vedi apps/identity/CLAUDE.md."""

    class DatePrecision(models.TextChoices):
        EXACT = "exact", _("Exact")
        MONTH = "month", _("Month")
        YEAR = "year", _("Year")
        DECADE = "decade", _("Decade")
        UNKNOWN = "unknown", _("Unknown")

    class Gender(models.TextChoices):
        MALE = "male", _("Male")
        FEMALE = "female", _("Female")
        NON_BINARY = "non_binary", _("Non-binary")
        UNKNOWN = "unknown", _("Unknown")
        OTHER = "other", _("Other")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # NOTE: la relazione User<->Person è dichiarata SOLO su User.person
    # (related_name='user_account'). Person accede al suo User via
    # `person.user_account`. Vedi docstring del modulo.

    given_names = models.CharField(max_length=200)
    surname = models.CharField(max_length=200)
    surname_at_birth = models.CharField(max_length=200, null=True, blank=True)
    nicknames = ArrayField(
        models.CharField(max_length=100),
        default=list,
        blank=True,
    )

    is_living = models.BooleanField()

    birth_date = models.DateField(null=True, blank=True)
    birth_date_precision = models.CharField(
        max_length=10,
        choices=DatePrecision.choices,
        default=DatePrecision.UNKNOWN,
    )
    birth_place = models.CharField(max_length=255, null=True, blank=True)

    death_date = models.DateField(null=True, blank=True)
    death_date_precision = models.CharField(
        max_length=10,
        choices=DatePrecision.choices,
        default=DatePrecision.UNKNOWN,
    )
    death_place = models.CharField(max_length=255, null=True, blank=True)

    gender = models.CharField(
        max_length=20,
        choices=Gender.choices,
        default=Gender.UNKNOWN,
    )

    # FK a content.Content quando esiste, M4
    profile_photo_content_id = models.UUIDField(null=True, blank=True)

    short_bio = models.TextField(null=True, blank=True)

    is_claimed = models.BooleanField(default=False)
    created_by_user = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        related_name="created_persons",
        null=True,  # nullable for chicken-and-egg of self-registration
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "identity_persons"
        verbose_name = "person"
        verbose_name_plural = "persons"
        indexes = [
            models.Index(fields=["surname", "given_names"]),
            models.Index(fields=["is_living"]),
            models.Index(fields=["archived_at"]),
            models.Index(fields=["created_by_user"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(is_living=True) | Q(death_date__isnull=False),
                name="person_dead_must_have_death_date",
            ),
            models.CheckConstraint(
                condition=(
                    Q(birth_date__isnull=True)
                    | Q(death_date__isnull=True)
                    | Q(birth_date__lte=F("death_date"))
                ),
                name="person_birth_before_death",
            ),
        ]

    def __str__(self):
        return f"{self.given_names} {self.surname}"


# ---------------------------------------------------------------------------
# PersonClaim
# ---------------------------------------------------------------------------
class PersonClaim(models.Model):
    """Richiesta di un User di rivendicare una Person esistente."""

    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        APPROVED = "approved", _("Approved")
        REJECTED = "rejected", _("Rejected")
        EXPIRED = "expired", _("Expired")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    person = models.ForeignKey(
        "identity.Person",
        on_delete=models.PROTECT,
        related_name="claims",
    )
    claiming_user = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        related_name="person_claims",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by_user = models.ForeignKey(
        "identity.User",
        on_delete=models.SET_NULL,
        related_name="resolved_claims",
        null=True,
        blank=True,
    )
    rejection_reason = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "identity_person_claims"
        verbose_name = "person claim"
        verbose_name_plural = "person claims"
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["person", "status"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["person", "claiming_user"],
                condition=Q(status="pending"),
                name="unique_pending_claim_per_person_user",
            ),
        ]

    def __str__(self):
        return f"Claim({self.person_id}, {self.claiming_user_id}, {self.status})"


# ---------------------------------------------------------------------------
# Invitation
# ---------------------------------------------------------------------------
class Invitation(models.Model):
    """Invito a un futuro utente, opzionalmente legato a una Person target."""

    class Status(models.TextChoices):
        SENT = "sent", _("Sent")
        ACCEPTED = "accepted", _("Accepted")
        REVOKED = "revoked", _("Revoked")
        EXPIRED = "expired", _("Expired")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invited_email = models.EmailField()
    target_person = models.ForeignKey(
        "identity.Person",
        on_delete=models.SET_NULL,
        related_name="invitations",
        null=True,
        blank=True,
    )
    inviter_user = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        related_name="sent_invitations",
    )
    token = models.CharField(max_length=128, unique=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SENT,
    )
    message = models.TextField(null=True, blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()

    class Meta:
        db_table = "identity_invitations"
        verbose_name = "invitation"
        verbose_name_plural = "invitations"
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["invited_email"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self):
        return f"Invitation({self.invited_email}, {self.status})"
