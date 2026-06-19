"""
auditlog/models.py

Tracks every significant action performed by any user across the platform.
Owners and Managers can browse the full log to see who changed what and when.

Design:
  - Signal-based: models connect to Django's post_save / post_delete signals
    so no individual view needs to call the logger manually.
  - Per-greenhouse scoping: every log entry is tied to a greenhouse so owners
    only see their own greenhouse's activity.
  - JSON diff: the `diff` field stores what actually changed (before/after)
    for UPDATE actions, making the log actionable, not just informational.
  - Read-only by design: AuditLog entries are NEVER updated or deleted.
    They are an immutable record.

Entities tracked (configured in apps.py via signals):
  - Operation (create, update, delete)
  - OperationPhoto (create, delete)
  - InventoryItem (create, update, delete)
  - InventoryTransaction (create, delete)
  - Sale (create, update, delete)
  - Expense (create, update, delete)
  - Crop (create, update, delete)
  - Bed (create, update, delete)
  - House (create, update, delete)
  - GreenhouseMembership (create, update, delete)
"""

import json
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class AuditLog(models.Model):

    class Action(models.TextChoices):
        CREATE = 'create', _('ایجاد شده')
        UPDATE = 'update', _('به‌روزرسانی شده')
        DELETE = 'delete', _('حذف شده')

    # ── Who ──────────────────────────────────────────────────────────
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='audit_logs',
        help_text=_('User who performed the action'),
    )
    # Snapshot of username at time of action — survives user deletion
    username_snapshot = models.CharField(
        max_length=150,
        blank=True,
        default='',
        help_text=_('Username captured at time of action, in case user is later deleted'),
    )

    # ── Where ─────────────────────────────────────────────────────────
    greenhouse = models.ForeignKey(
        'greenhouse_app.Greenhouse',
        on_delete=models.CASCADE,
        related_name='audit_logs',
        null=True,
        blank=True,
        help_text=_('Greenhouse this action belongs to — used for owner/manager filtering'),
    )

    # ── What ──────────────────────────────────────────────────────────
    action = models.CharField(
        max_length=10,
        choices=Action.choices,
        db_index=True,
    )
    entity_type = models.CharField(
        max_length=100,
        db_index=True,
        help_text=_('Model name, e.g. "Operation", "Sale", "InventoryItem"'),
    )
    entity_id = models.PositiveIntegerField(
        null=True,
        help_text=_('Primary key of the affected record'),
    )
    entity_label = models.CharField(
        max_length=300,
        blank=True,
        default='',
        help_text=_('Human-readable string representation of the record at time of action'),
    )

    # ── Detail ────────────────────────────────────────────────────────
    diff = models.JSONField(
        null=True,
        blank=True,
        help_text=_(
            'For UPDATE: {"field": {"before": old_val, "after": new_val}, ...}. '
            'For CREATE: the new values. For DELETE: the final values before deletion.'
        ),
    )
    notes = models.CharField(
        max_length=500,
        blank=True,
        default='',
        help_text=_('Optional context added by the signal handler'),
    )

    # ── When ──────────────────────────────────────────────────────────
    timestamp = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )

    class Meta:
        db_table = 'audit_logs'
        verbose_name = _('Audit Log Entry')
        verbose_name_plural = _('Audit Log')
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['greenhouse', '-timestamp']),
            models.Index(fields=['entity_type', 'entity_id']),
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['action', '-timestamp']),
        ]

    def __str__(self):
        user_str = self.username_snapshot or 'Unknown'
        return (
            f'[{self.timestamp:%Y-%m-%d %H:%M}] '
            f'{user_str} {self.get_action_display()} '
            f'{self.entity_type} #{self.entity_id}'
        )

    @property
    def diff_summary(self):
        """Returns a short human-readable summary of what changed."""
        if not self.diff:
            return ''
        if self.action == self.Action.UPDATE:
            fields = list(self.diff.keys())
            if len(fields) <= 3:
                return ', '.join(fields)
            return f'{", ".join(fields[:3])} +{len(fields)-3} more'
        return ''
