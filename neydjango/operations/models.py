"""
operations/models.py

The Operations app records every daily field action performed on a bed.
This is the core activity log of the platform — the document calls it
"یکپارچه‌سازی مدیریت عملیات، مالی و فروش" (unified operations management).

Every operation is tied to a Bed (the smallest physical unit) and has:
  - a type (irrigation, fertilizing, spraying, harvesting, etc.)
  - quantities and units
  - the operator who logged it
  - optional notes and photos

Operation types from the business document:
  IRRIGATION   — آبیاری
  FERTILIZING  — کود‌دهی
  SPRAYING     — سم‌پاشی
  HARVESTING   — برداشت
  PRUNING      — هرس
  TRANSPLANT   — نشاء
  INSPECTION   — بازدید / بررسی
  OTHER        — سایر

The document also specifies that operations feed into:
  - Financial reports (cost per operation)
  - AI analysis (pattern detection, disease correlation)
  - Harvest yield tracking

Design decisions:
  - One Operation = one action on one bed on one date
  - quantity + unit captures how much was used (e.g. 5 litres of fertilizer)
  - cost captures the direct cost of this operation (labour + materials)
  - OperationPhoto allows multiple photos per operation (for disease detection)
"""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Operation(models.Model):

    class Type(models.TextChoices):
        IRRIGATION  = 'irrigation',  _('Irrigation')       # آبیاری
        FERTILIZING = 'fertilizing', _('Fertilizing')      # کود‌دهی
        SPRAYING    = 'spraying',    _('Spraying')          # سم‌پاشی
        HARVESTING  = 'harvesting',  _('Harvesting')        # برداشت
        PRUNING     = 'pruning',     _('Pruning')           # هرس
        TRANSPLANT  = 'transplant',  _('Transplanting')     # نشاء
        INSPECTION  = 'inspection',  _('Inspection')        # بازدید
        OTHER       = 'other',       _('Other')             # سایر

    class Unit(models.TextChoices):
        LITRE      = 'litre',      _('Litre (L)')
        KILOGRAM   = 'kilogram',   _('Kilogram (kg)')
        GRAM       = 'gram',       _('Gram (g)')
        PIECE      = 'piece',      _('Piece / Unit')
        HOUR       = 'hour',       _('Hour')
        SQUARE_M   = 'square_m',   _('Square Metre (m²)')
        OTHER      = 'other',      _('Other')

    # ── Core relations ───────────────────────────────────────────────
    bed = models.ForeignKey(
        'greenhouse_app.Bed',
        on_delete=models.CASCADE,
        related_name='operations',
        help_text=_('Which bed this operation was performed on'),
    )
    crop = models.ForeignKey(
        'greenhouse_app.Crop',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='operations',
        help_text=_('Active crop at the time — auto-linked or manually selected'),
    )
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='operations_performed',
        help_text=_('Operator who carried out the work'),
    )
    logged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='operations_logged',
        help_text=_('User who entered this record (may differ from performer)'),
    )

    # ── What was done ────────────────────────────────────────────────
    operation_type = models.CharField(
        max_length=30,
        choices=Type.choices,
        db_index=True,
    )
    performed_at = models.DateField(
        help_text=_('Date the operation actually happened'),
        db_index=True,
    )

    # ── Quantity ─────────────────────────────────────────────────────
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
        help_text=_('Amount used, e.g. 5.0 litres of fertilizer'),
    )
    unit = models.CharField(
        max_length=20,
        choices=Unit.choices,
        blank=True,
        default='',
    )

    # ── Product / Material ───────────────────────────────────────────
    product_name = models.CharField(
        max_length=200,
        blank=True,
        default='',
        help_text=_('Name of fertilizer, pesticide, or seed used'),
    )
    product_batch = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text=_('Batch or lot number for traceability'),
    )

    # ── Financials ───────────────────────────────────────────────────
    cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_('Direct cost of this operation in local currency'),
    )

    # ── Harvest specific ─────────────────────────────────────────────
    harvest_weight_kg = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
        help_text=_('Weight harvested in kg — only for HARVESTING operations'),
    )
    harvest_quality = models.CharField(
        max_length=20,
        blank=True,
        default='',
        choices=[
            ('grade_a', _('Grade A')),
            ('grade_b', _('Grade B')),
            ('grade_c', _('Grade C')),
            ('rejected', _('Rejected')),
        ],
        help_text=_('Quality grade of harvested produce'),
    )

    # ── Notes ────────────────────────────────────────────────────────
    notes = models.TextField(
        blank=True,
        default='',
        help_text=_('Observations, issues, or free-form notes'),
    )

    # ── Timestamps ───────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'operations'
        verbose_name = _('Operation')
        verbose_name_plural = _('Operations')
        ordering = ['-performed_at', '-created_at']
        indexes = [
            models.Index(fields=['performed_at', 'operation_type']),
            models.Index(fields=['bed', 'performed_at']),
        ]

    def __str__(self):
        return (
            f'{self.get_operation_type_display()} '
            f'@ {self.bed} '
            f'on {self.performed_at}'
        )

    @property
    def greenhouse(self):
        return self.bed.house.greenhouse


class OperationPhoto(models.Model):
    """
    One or more photos attached to an operation.
    Primary use: disease detection (Module 3 — AI image analysis).
    Photos are uploaded per-operation and later sent to the
    FastAPI ML inference service.
    """
    operation = models.ForeignKey(
        Operation,
        on_delete=models.CASCADE,
        related_name='photos',
    )
    image = models.ImageField(
        upload_to='operations/photos/%Y/%m/',
        help_text=_('Photo of the crop, bed, or issue observed'),
    )
    caption = models.CharField(
        max_length=200,
        blank=True,
        default='',
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'operation_photos'
        verbose_name = _('Operation Photo')
        verbose_name_plural = _('Operation Photos')

    def __str__(self):
        return f'Photo for {self.operation} ({self.uploaded_at.date()})'
