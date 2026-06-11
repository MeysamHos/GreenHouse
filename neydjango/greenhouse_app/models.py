from django.db import models
from django.conf import settings


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
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    location_geojson = models.TextField(
        blank=True,
        help_text='GeoJSON point string. Example: {"type":"Point","coordinates":[51.38,35.68]}'
    )
    timezone = models.CharField(
        max_length=60,
        default='Asia/Tehran',
        help_text="Timezone for date/time calculations. E.g. Asia/Tehran"
    )
    total_area_m2 = models.DecimalField(
    max_digits=10, decimal_places=2,
    null=True, blank=True,
    help_text="Total greenhouse area in square metres"
    )
    is_active = models.BooleanField(default=True)
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
        help_text="E.g. 'Hall A', 'North Section', 'سالن ۱'"
    )
    area_m2 = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Floor area in square meters."
    )
    notes = models.TextField(blank=True)
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
        help_text="Short identifier, e.g. 'B-01', 'Row-3'"
    )
    area_m2 = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True
    )
    capacity = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Max number of plants this bed holds."
    )
    notes = models.TextField(blank=True)
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
        PLANNED   = 'planned',   'Planned'
        GROWING   = 'growing',   'Growing'
        HARVESTED = 'harvested', 'Harvested'
        FAILED    = 'failed',    'Failed'

    bed = models.ForeignKey(
        Bed,
        on_delete=models.CASCADE,
        related_name='crops'
    )
    crop_type = models.CharField(
        max_length=100,
        help_text="Type of crop. E.g. 'Tomato', 'Cucumber', 'گوجه فرنگی'"
    )
    variety = models.CharField(
        max_length=100,
        blank=True,
        help_text="Specific variety/cultivar. E.g. 'Cherry 100F1', 'Superstar'"
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PLANNED
    )
    planted_at = models.DateField(
        null=True,
        blank=True,
        help_text="Actual planting date."
    )
    expected_harvest_at = models.DateField(
        null=True,
        blank=True,
        help_text="Estimated harvest date, calculated from planting + crop cycle length."
    )
    actual_harvest_at = models.DateField(
        null=True,
        blank=True,
        help_text="Filled when status → HARVESTED."
    )
    plant_count = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Number of plants in this crop cycle."
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-planted_at']

    def __str__(self):
        return f"{self.crop_type} ({self.variety}) @ {self.bed} [{self.status}]"

    @property
    def greenhouse(self):
        """Convenience shortcut: crop.greenhouse"""
        return self.bed.house.greenhouse
