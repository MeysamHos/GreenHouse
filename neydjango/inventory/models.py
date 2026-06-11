"""
inventory/models.py

Tracks all materials (inputs) and produce (outputs) in the greenhouse.

Design philosophy:
  - Never store "current stock" as a number — it's always derived from transactions.
    This is the standard accounting approach: current_stock = sum of all IN - sum of all OUT.
    It gives a full audit trail and makes it impossible to have unexplained stock changes.

  - InventoryItem  → the "product card" (what it is, its unit, thresholds)
  - InventoryTransaction → every movement (purchase, consumption, harvest, adjustment)

Categories (from the business document):
  - FERTILIZER  کود
  - PESTICIDE   سم
  - SEED        بذر
  - TOOL        ابزار
  - PACKAGING   بسته‌بندی
  - PRODUCE     محصول برداشت شده
  - OTHER       سایر
"""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class InventoryItem(models.Model):
    """
    A product/material tracked in inventory.
    Think of this as the "product card" — it defines what the item is,
    how it's measured, and what the minimum stock threshold is.

    One InventoryItem can exist across multiple greenhouses by design —
    "NPK Fertilizer 20-20-20" is the same product everywhere.
    Stock levels are per-greenhouse via transactions.
    """

    class Category(models.TextChoices):
        FERTILIZER = 'fertilizer', _('Fertilizer')    # کود
        PESTICIDE  = 'pesticide',  _('Pesticide')     # سم
        SEED       = 'seed',       _('Seed')           # بذر
        TOOL       = 'tool',       _('Tool')           # ابزار
        PACKAGING  = 'packaging',  _('Packaging')      # بسته‌بندی
        PRODUCE    = 'produce',    _('Harvested Produce')  # محصول
        OTHER      = 'other',      _('Other')

    class Unit(models.TextChoices):
        KILOGRAM   = 'kg',    _('Kilogram (kg)')
        GRAM       = 'g',     _('Gram (g)')
        LITRE      = 'l',     _('Litre (L)')
        MILLILITRE = 'ml',    _('Millilitre (mL)')
        PIECE      = 'piece', _('Piece / Unit')
        BOX        = 'box',   _('Box')
        BAG        = 'bag',   _('Bag')
        OTHER      = 'other', _('Other')

    greenhouse = models.ForeignKey(
        'greenhouse_app.Greenhouse',
        on_delete=models.CASCADE,
        related_name='inventory_items',
    )

    name = models.CharField(
        max_length=200,
        help_text=_('e.g. NPK 20-20-20, Chlorpyrifos, Tomato Seeds F1'),
    )
    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        db_index=True,
    )
    unit = models.CharField(
        max_length=10,
        choices=Unit.choices,
    )
    brand = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text=_('Brand or manufacturer name'),
    )
    description = models.TextField(blank=True, default='')

    # Stock alert threshold
    min_stock_threshold = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
        help_text=_('Alert when stock falls below this level'),
    )

    # Unit cost for financial calculations
    unit_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_('Cost per unit in local currency — updated on each purchase'),
    )

    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_inventory_items',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'inventory_items'
        verbose_name = _('Inventory Item')
        verbose_name_plural = _('Inventory Items')
        ordering = ['category', 'name']
        unique_together = [('greenhouse', 'name')]

    def __str__(self):
        return f'{self.name} ({self.get_unit_display()})'

    def current_stock(self, greenhouse=None):
        """
        Calculate current stock from all transactions.
        IN transactions increase stock, OUT transactions decrease it.
        """
        from django.db.models import Sum
        qs = self.transactions.all()
        total_in  = qs.filter(
            transaction_type__in=['purchase', 'adjustment_in', 'harvest']
        ).aggregate(t=Sum('quantity'))['t'] or 0
        total_out = qs.filter(
            transaction_type__in=['consumption', 'adjustment_out', 'waste']
        ).aggregate(t=Sum('quantity'))['t'] or 0
        return total_in - total_out

    @property
    def is_low_stock(self):
        if self.min_stock_threshold is None:
            return False
        return self.current_stock() <= self.min_stock_threshold


class InventoryTransaction(models.Model):
    """
    Every stock movement — in or out.

    Transaction types:
      PURCHASE       → bought materials (stock IN)
      CONSUMPTION    → used in an operation (stock OUT)
      HARVEST        → produce added to inventory (stock IN)
      ADJUSTMENT_IN  → manual correction upward (stock IN)
      ADJUSTMENT_OUT → manual correction downward (stock OUT)
      WASTE          → spoilage or loss (stock OUT)
    """

    class TransactionType(models.TextChoices):
        PURCHASE       = 'purchase',       _('Purchase')         # خرید
        CONSUMPTION    = 'consumption',    _('Consumption')      # مصرف
        HARVEST        = 'harvest',        _('Harvest')          # برداشت
        ADJUSTMENT_IN  = 'adjustment_in',  _('Adjustment (In)')  # تعدیل مثبت
        ADJUSTMENT_OUT = 'adjustment_out', _('Adjustment (Out)') # تعدیل منفی
        WASTE          = 'waste',          _('Waste / Loss')     # ضایعات

    item = models.ForeignKey(
        InventoryItem,
        on_delete=models.CASCADE,
        related_name='transactions',
    )

    transaction_type = models.CharField(
        max_length=20,
        choices=TransactionType.choices,
        db_index=True,
    )

    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        help_text=_('Always positive — direction is determined by transaction_type'),
    )

    # Financial
    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_('Price per unit for this transaction'),
    )

    @property
    def total_cost(self):
        if self.unit_price and self.quantity:
            return self.unit_price * self.quantity
        return None

    # Links to other apps
    operation = models.ForeignKey(
        'operations.Operation',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inventory_transactions',
        help_text=_('Operation that triggered this transaction (consumption/harvest)'),
    )

    # Supplier info (for purchases)
    supplier_name = models.CharField(max_length=200, blank=True, default='')
    invoice_number = models.CharField(max_length=100, blank=True, default='')

    # Batch tracking
    batch_number = models.CharField(max_length=100, blank=True, default='')
    expiry_date = models.DateField(null=True, blank=True)

    notes = models.TextField(blank=True, default='')

    performed_at = models.DateField(
        help_text=_('Date the transaction occurred'),
        db_index=True,
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='inventory_transactions_recorded',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'inventory_transactions'
        verbose_name = _('Inventory Transaction')
        verbose_name_plural = _('Inventory Transactions')
        ordering = ['-performed_at', '-created_at']
        indexes = [
            models.Index(fields=['performed_at', 'transaction_type']),
            models.Index(fields=['item', 'performed_at']),
        ]

    def __str__(self):
        return (
            f'{self.get_transaction_type_display()} — '
            f'{self.quantity} {self.item.get_unit_display()} '
            f'of {self.item.name} '
            f'on {self.performed_at}'
        )
