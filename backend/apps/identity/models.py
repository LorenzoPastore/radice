from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Custom User model. Extends AbstractUser.
    Email is the login credential (username field kept for admin compatibility).
    Full profile data lives on the associated Person (implemented in Milestone 1).
    """
    email = models.EmailField(unique=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        db_table = "identity_users"
        verbose_name = "user"
        verbose_name_plural = "users"
