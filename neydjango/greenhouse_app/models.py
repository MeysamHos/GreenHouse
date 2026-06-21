from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _

class Greenhouse(models.Model):
    """
    The top-level entity. Everything in the system belongs to a Greenhouse.

    owner: the user who created it. This is separate from GreenhouseMembership
    — the owner always has full access regardless of membership records,
    and is the billing contact.

    location_geojson: stores GPS coordinates as a simple JSON string.
    Example: {"type": "Point", "coordinates": [51.3890, 35.6892]}
    We use a plain TextField here to avoid requiring PostGIS extension.
    In a later phase this can be upgraded to a proper GeoDjango PointField.

    timezone: important for correct date calculations on operations and reports.
    Example: "Asia/Tehran"
    """
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,      # don't delete greenhouse if owner is deleted
        related_name='owned_greenhouses_app'
    )
    name = models.CharField(max_length=200, verbose_name="نام")
    description = models.TextField(blank=True, verbose_name="توضیحات")
    location_geojson = models.TextField(
        blank=True,
        help_text='GeoJSON point string. Example: {"type":"Point","coordinates":[51.38,35.68]}',
        verbose_name="موقعیت مکانی GeoJSON"
    )
    timezone = models.CharField(
        max_length=60,
        default='Asia/Tehran',
        help_text="منطقه زمانی برای محاسبات تاریخ و زمان. برای مثال: Asia/Tehran",
        verbose_name="منطقه زمانی"
    )
    total_area_m2 = models.DecimalField(
    max_digits=10, decimal_places=2,
    null=True, blank=True,
    help_text="مساحت کل گلخانه به متر مربع",
    verbose_name="مجموع مساحت به متر مربع"
    )
    is_active = models.BooleanField(default=True, verbose_name="فعال است؟")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class House(models.Model):
    """
    A physical hall or section inside a greenhouse. Called 'سالن' in the docs.

    Example: "Greenhouse North" might have House A (tomatoes) and House B (cucumbers).

    area_m2: floor area in square meters — used for cost-per-m2 reporting.
    """
    greenhouse = models.ForeignKey(
        Greenhouse,
        on_delete=models.CASCADE,
        related_name='houses'
    )
    name = models.CharField(
        max_length=100,
        help_text="مانند 'Hall A', 'North Section', 'سالن ۱'",
        verbose_name="نام"
    )
    area_m2 = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="مساحت کف به متر مربع",
        verbose_name="مساحت به متر مربع"
    )
    notes = models.TextField(blank=True, verbose_name="یادداشت")
    created_at = models.DateTimeField(auto_now_add=True)


    class Meta:
        ordering = ['greenhouse', 'name']
        unique_together = ('greenhouse', 'name')

    def __str__(self):
        return f"{self.greenhouse.name} / {self.name}"


class Bed(models.Model):
    """
    A growing bed inside a House. Called 'بستر' in the docs.

    This is the most granular physical unit. Operations (irrigation,
    fertilizing, spraying) are always attached to a Bed.

    code: short identifier used in daily operations. E.g. "B-01", "R3-L2"
    capacity: number of plants this bed can hold
    """
    house = models.ForeignKey(
        House,
        on_delete=models.CASCADE,
        related_name='beds'
    )
    code = models.CharField(
        max_length=50,
        help_text="شناسه کوتاه، برای مثال: 'B-01'، 'Row-3'",
        verbose_name="شناسه"
    )
    area_m2 = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="مساحت به متر مربع"
    )
    capacity = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="حداکثر تعداد گیاهی که این بستر در خود جای می‌دهد.",
        verbose_name="ظرفیت"
    )
    notes = models.TextField(blank=True, verbose_name="یادداشت")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['house', 'code']
        unique_together = ('house', 'code')

    def __str__(self):
        return f"{self.house} / {self.code}"

    @property
    def greenhouse(self):
        """Convenience shortcut: bed.greenhouse instead of bed.house.greenhouse"""
        return self.house.greenhouse


class Crop(models.Model):
    """
    A planting record. Represents one crop cycle on a specific Bed.

    One bed can have many crops over time (sequential crop cycles),
    but only one ACTIVE crop at a time. We enforce this via status.

    This is the entity that operations, AI recommendations, and financial
    reports will primarily reference.

    status lifecycle:
        PLANNED   → seed ordered but not planted yet
        GROWING   → currently in the ground
        HARVESTED → cycle complete
        FAILED    → crop was lost (disease, weather, etc.)
    """

    class Status(models.TextChoices):
        PLANNED   = 'planned',   'کاشته شده'
        GROWING   = 'growing',   'در حال رشد'
        HARVESTED = 'harvested', 'برداشت شده'
        FAILED    = 'failed',    'ناموفق'

    bed = models.ForeignKey(
        Bed,
        on_delete=models.CASCADE,
        related_name='crops'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_crops',
        help_text="کاربری که این دوره کاشت را ایجاد کرده است.",
        verbose_name="ایجاد شده توسط",
    )
    crop_type = models.CharField(
        max_length=100,
        help_text="نوع محصول. برای مثال: «Tomato» (گوجه‌فرنگی)، «Cucumber» (خیار)، «گوجه فرنگی»",
        verbose_name="نوع محصول"
    )
    variety = models.CharField(
        max_length=100,
        blank=True,
        help_text="گونه/رقم خاص (گیاه). برای مثال: «Cherry 100F1»، «Superstar»",
        verbose_name="گونه"
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PLANNED,
        verbose_name="وضعیت"
    )
    planted_at = models.DateField(
        null=True,
        blank=True,
        help_text="تاریخ دقیق کاشت.",
        verbose_name="زمان کاشت"
    )
    expected_harvest_at = models.DateField(
        null=True,
        blank=True,
        help_text="تاریخ برداشت تخمینی، محاسبه‌شده از زمان کاشت + طول دوره رشد",
        verbose_name="تاریخ برداشت تخمینی"
    )
    actual_harvest_at = models.DateField(
        null=True,
        blank=True,
        help_text="زمانی که وضعیت به «برداشت‌شده» تغییر کند،تکمیل می‌گردد.",
        verbose_name="تاریخ برداشت"
    )
    plant_count = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="تعداد گیاهان در این دوره کاشت",
        verbose_name="تعداد گیاهان"
    )
    applied_template = models.ForeignKey(
        'operations.CropOperationTemplate',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='applied_to_crops',
        help_text=_(
            'در صورت اعمال «عملیات پیشنهادی»، قالب استفاده‌شده اینجا ثبت می‌شود. '
            'برای جلوگیری از اعمال دوباره و نمایش وضعیت استفاده می‌شود.'
        ),
        verbose_name=_('قالب اعمال‌شده'),
    )
    notes = models.TextField(blank=True, verbose_name="یادداشت")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-planted_at']

    def __str__(self):
        return f"{self.crop_type} ({self.variety}) @ {self.bed} [{self.get_status_display()}]"

    @property
    def greenhouse(self):
        """Convenience shortcut: crop.greenhouse"""
        return self.bed.house.greenhouse
