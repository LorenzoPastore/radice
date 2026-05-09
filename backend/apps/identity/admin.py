from django.contrib import admin

from .models import Invitation, Person, PersonClaim, User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = (
        "email",
        "display_name",
        "is_active",
        "email_verified_at",
        "created_at",
    )
    list_filter = ("is_active", "is_staff", "privacy_preset", "email_verified_at")
    search_fields = ("email", "display_name")
    ordering = ("-created_at",)
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
        "last_login",
        "last_login_at",
    )


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = (
        "surname",
        "given_names",
        "is_living",
        "is_claimed",
        "created_at",
    )
    list_filter = ("is_living", "is_claimed", "gender")
    search_fields = ("given_names", "surname", "nicknames")


@admin.register(PersonClaim)
class PersonClaimAdmin(admin.ModelAdmin):
    list_display = ("person", "claiming_user", "status", "requested_at")
    list_filter = ("status",)


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = (
        "invited_email",
        "inviter_user",
        "status",
        "sent_at",
        "expires_at",
    )
    list_filter = ("status",)
    search_fields = ("invited_email",)
