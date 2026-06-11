"""
financials/models.py

The Financials app is the economic brain of the platform.

It does NOT duplicate cost data already stored in operations or inventory —
instead it AGGREGATES those sources plus two new models:

  Sale             → revenue when harvested produce is sold
  Expense          → overhead costs not tied to a specific operation
                     (rent, utilities, labour contracts, equipment)

P&L for any period = Revenue (Sales) − Costs (Operations + Purchases + Expenses)

Design decisions:
  - Sale links to a Crop so we can compute per-crop and per-bed profitability
  - Expense has a category enum matching standard farm accounting buckets
  - Both are scoped to a Greenhouse (not a user) — financials belong to the farm
  - The PnLReport is NOT stored — it's always computed on demand from live data
    so there's no stale data problem
"""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Sale(models.Model):
    """
    A sale of harvested produce to a buyer.

    Links to a Crop so we know which bed/house produced this revenue.
    One crop cycle can have multiple partial sales (e.g. sold in batches).
    """

    class PaymentStatus(models.TextChoices):
        PENDING  = 'pending',  _('Pending')
        PAID     = 'paid',     _('Paid')
        PARTIAL  = 'partial',  _('Partially Paid')
        OVERDUE  = 'overdue',  _('Overdue')
        CANCELLED = 'cancelled', _('Cancelled')

    greenhouse = models.ForeignKey(
        'greenhouse_app.Greenhouse',
        on_delete=models.CASCADE,
        related_name='sales',
    )
    crop = models.ForeignKey(
        'greenhouse_app.Crop',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sales',
        help_text=_('Crop cycle this sale came from'),
    )

    # Buyer
    buyer_name = models.CharField(
        max_length=200,
        help_text=_('Name of buyer / company / market'),
    )
    buyer_phone = models.CharField(max_length=20, blank=True, default='')

    # What was sold
    product_name = models.CharField(
        max_length=200,
        help_text=_('e.g. Cherry Tomato Grade A'),
    )
    quantity_kg = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        help_text=_('Weight sold in kilograms'),
    )
    price_per_kg = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text=_('Sale price per kg in local currency'),
    )

    @property
    def total_amount(self):
        return self.quantity_kg * self.price_per_kg

    # Payment tracking
    payment_status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
        db_index=True,
    )
    amount_paid = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text=_('Amount actually received so far'),
    )
    invoice_number = models.CharField(max_length=100, blank=True, default='')

    sold_at = models.DateField(
        help_text=_('Date of sale / delivery'),
        db_index=True,
    )
    notes = models.TextField(blank=True, default='')

    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='sales_recorded',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sales'
        verbose_name = _('Sale')
        verbose_name_plural = _('Sales')
        ordering = ['-sold_at', '-created_at']
        indexes = [
            models.Index(fields=['sold_at', 'payment_status']),
            models.Index(fields=['greenhouse', 'sold_at']),
        ]

    def __str__(self):
        return (
            f'Sale {self.quantity_kg}kg @ {self.price_per_kg} '
            f'to {self.buyer_name} on {self.sold_at}'
        )

    @property
    def amount_outstanding(self):
        return self.total_amount - self.amount_paid


class Expense(models.Model):
    """
    Overhead / fixed costs that are NOT tied to a specific operation.

    Examples:
      - Monthly greenhouse rent
      - Electricity bill
      - Seasonal labour contract
      - Equipment maintenance
      - Insurance

    These are separate from Operation.cost (per-action variable costs)
    and InventoryTransaction.unit_price (material purchases).
    Together all three = total cost.
    """

    class Category(models.TextChoices):
        RENT        = 'rent',        _('Rent / Land')
        UTILITIES   = 'utilities',   _('Utilities (Water, Electricity, Gas)')
        LABOUR      = 'labour',      _('Labour / Wages')
        EQUIPMENT   = 'equipment',   _('Equipment & Maintenance')
        TRANSPORT   = 'transport',   _('Transport & Logistics')
        INSURANCE   = 'insurance',   _('Insurance')
        MARKETING   = 'marketing',   _('Marketing & Sales')
        ADMIN       = 'admin',       _('Administrative & Office')
        OTHER       = 'other',       _('Other')

    greenhouse = models.ForeignKey(
        'greenhouse_app.Greenhouse',
        on_delete=models.CASCADE,
        related_name='expenses',
    )

    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        db_index=True,
    )
    description = models.CharField(
        max_length=300,
        help_text=_('What this expense was for'),
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text=_('Total amount in local currency'),
    )

    # Optional: link to a specific house or crop for per-unit cost tracking
    house = models.ForeignKey(
        'greenhouse_app.House',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='expenses',
        help_text=_('Optionally attribute this expense to a specific hall/section'),
    )

    expense_date = models.DateField(db_index=True)
    invoice_number = models.CharField(max_length=100, blank=True, default='')
    vendor_name = models.CharField(max_length=200, blank=True, default='')
    notes = models.TextField(blank=True, default='')

    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='expenses_recorded',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'expenses'
        verbose_name = _('Expense')
        verbose_name_plural = _('Expenses')
        ordering = ['-expense_date', '-created_at']
        indexes = [
            models.Index(fields=['expense_date', 'category']),
            models.Index(fields=['greenhouse', 'expense_date']),
        ]

    def __str__(self):
        return f'{self.get_category_display()} — {self.description} ({self.amount})'
