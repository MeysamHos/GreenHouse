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
        PENDING  = 'pending',  _('در انتظار')
        PAID     = 'paid',     _('پرداخت شده')
        PARTIAL  = 'partial',  _('تا حدی پرداخت شده')
        OVERDUE  = 'overdue',  _('معوقه')
        CANCELLED = 'cancelled', _('لغو شده')

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
        help_text=_('چرخه زراعی این فروش'),
        verbose_name="محصول"
    )

    # Buyer
    buyer_name = models.CharField(
        max_length=200,
        help_text=_('نام خریدار / شرکت / بازار'),
        verbose_name="خریدار"
    )
    buyer_phone = models.CharField(max_length=20, blank=True, default='', verbose_name="شماره تماس خریدار")

    # What was sold
    product_name = models.CharField(
        max_length=200,
        help_text=_('مانند گوجه فرنگی درجه یک'),
        verbose_name="نام محصول"
    )
    quantity_kg = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        help_text=_('وزن فروخته شده به کیلوگرم'),
        verbose_name="مقدار کیلوگرم"
    )
    price_per_kg = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text=_('قیمت فروش هر کیلوگرم از محصول'),
        verbose_name="قیمت هر کیلو"
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
        verbose_name="وضعیت پرداخت"
    )
    amount_paid = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text=_('مبلغی که تا کنون دریافت شده است'),
        verbose_name="مقدار پرداخت‌شده"
    )
    invoice_number = models.CharField(max_length=100, blank=True, default='', verbose_name="شماره فاکتور")

    sold_at = models.DateField(
        help_text=_('تاریخ فروش / ارسال'),
        db_index=True,
        verbose_name="زمان فروش"
    )
    notes = models.TextField(blank=True, default='', verbose_name="یادداشت")

    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='sales_recorded',
        verbose_name="ثبت شده توسط"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="زمان ایجاد")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="زمان بروزرسانی")

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
        RENT        = 'rent',        _('اجاره / زمین')
        UTILITIES   = 'utilities',   _('خدمات (آب، برق، گاز)')
        LABOUR      = 'labour',      _('کار / دستمزد')
        EQUIPMENT   = 'equipment',   _('تجهیزات و نگهداری')
        TRANSPORT   = 'transport',   _('حمل و نقل و لجستیک')
        INSURANCE   = 'insurance',   _('بیمه')
        MARKETING   = 'marketing',   _('بازاریابی و فروش')
        ADMIN       = 'admin',       _('اداری و دفتری')
        OTHER       = 'other',       _('متفرقه')

    greenhouse = models.ForeignKey(
        'greenhouse_app.Greenhouse',
        on_delete=models.CASCADE,
        related_name='expenses',
    )

    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        db_index=True,
        verbose_name="دسته‌بندی"
    )
    description = models.CharField(
        max_length=300,
        help_text=_('این هزینه برای چه بوده است.'),
        verbose_name="توضیح"
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text=_('مبلغ کل به پول محلی'),
        verbose_name="مبلغ کل"
    )

    # Optional: link to a specific house or crop for per-unit cost tracking
    house = models.ForeignKey(
        'greenhouse_app.House',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='expenses',
        help_text=_('اختصاص این هزینه به یک سالن/بخش خاص (اختیاری).'),
        verbose_name="سالن"
    )

    expense_date = models.DateField(db_index=True, verbose_name="تاریخ هزینه")
    invoice_number = models.CharField(max_length=100, blank=True, default='', verbose_name="شماره فاکتور")
    vendor_name = models.CharField(max_length=200, blank=True, default='', verbose_name="نام فروشنده")
    notes = models.TextField(blank=True, default='', verbose_name="یادداشت")

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
