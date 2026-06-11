from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Custom user model. We extend AbstractUser so we keep all of Django's
    built-in auth behaviour (password hashing, login, admin, etc.) while
    adding the fields this platform needs.

    IMPORTANT: settings.py must have AUTH_USER_MODEL = 'accounts.User'
    and this must exist BEFORE the first `manage.py migrate`.
    """

    class Locale(models.TextChoices):
        FA = 'fa', 'Persian'
        EN = 'en', 'English'

    phone = models.CharField(
        max_length=20,
        blank=True,
        help_text="User's mobile number, used for SMS notifications."
    )
    avatar = models.ImageField(
        upload_to='avatars/',
        null=True,
        blank=True
    )
    locale = models.CharField(
        max_length=5,
        choices=Locale.choices,
        default=Locale.FA,
        help_text="Preferred language for UI and notifications."
    )

    # AbstractUser already has: username, email, first_name, last_name,
    # is_active, is_staff, date_joined, last_login, password.
    # We intentionally do NOT add a global 'role' field here — roles are
    # per-greenhouse via greenhouseMembership below.

    def __str__(self):
        return self.get_full_name() or self.username


class GreenhouseMembership(models.Model):
    """
    The join table between User and greenhouse that carries the role.

    This is the correct long-term design: one user can be a Manager in
    greenhouse A and a Consultant in greenhouse B. Role is always evaluated
    in the context of a specific greenhouse.

    Role hierarchy (highest to lowest permission):
        OWNER      — full control, billing, can delete the greenhouse
        MANAGER    — full operational control, cannot delete greenhouse
        OPERATOR   — can log daily operations, cannot change structure
        CONSULTANT — read + add notes/recommendations, cannot change data
        GUEST      — read-only, no writes at all
    """

    class Role(models.TextChoices):
        OWNER      = 'owner',      'Owner'
        MANAGER    = 'manager',    'Manager'
        OPERATOR   = 'operator',   'Operator'
        CONSULTANT = 'consultant', 'Consultant'
        GUEST      = 'guest',      'Guest (Read-only)'

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='memberships'
    )
    greenhouse = models.ForeignKey(
        # String reference avoids circular import — greenhouse app is defined
        # separately. Django resolves this at runtime.
        'greenhouse_app.greenhouse',
        on_delete=models.CASCADE,
        related_name='memberships'
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.OPERATOR
    )
    joined_at = models.DateTimeField(auto_now_add=True)
    invited_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invitations_sent',
        help_text="Which user invited this member."
    )

    class Meta:
        # A user can only have one role per greenhouse.
        unique_together = ('user', 'greenhouse')
        ordering = ['joined_at']

    def __str__(self):
        return f"{self.user} — {self.get_role_display()} @ {self.greenhouse}"
