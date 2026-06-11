from django.contrib import admin
from .models import Greenhouse, House, Bed, Crop


class HouseInline(admin.TabularInline):
    model = House
    extra = 0
    show_change_link = True


class BedInline(admin.TabularInline):
    model = Bed
    extra = 0
    show_change_link = True


class CropInline(admin.TabularInline):
    model = Crop
    extra = 0
    fields = ('crop_type', 'variety', 'status', 'planted_at', 'expected_harvest_at')
    show_change_link = True


@admin.register(Greenhouse)
class GreenhouseAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'timezone', 'is_active', 'created_at')
    list_filter = ('is_active', 'timezone')
    search_fields = ('name', 'owner__username')
    inlines = [HouseInline]


@admin.register(House)
class HouseAdmin(admin.ModelAdmin):
    list_display = ('name', 'greenhouse', 'area_m2', 'created_at')
    search_fields = ('name', 'greenhouse__name')
    inlines = [BedInline]


@admin.register(Bed)
class BedAdmin(admin.ModelAdmin):
    list_display = ('code', 'house', 'area_m2', 'capacity', 'created_at')
    search_fields = ('code', 'house__name', 'house__greenhouse__name')
    inlines = [CropInline]


@admin.register(Crop)
class CropAdmin(admin.ModelAdmin):
    list_display = ('crop_type', 'variety', 'bed', 'status',
                    'planted_at', 'expected_harvest_at')
    list_filter = ('status', 'crop_type')
    search_fields = ('crop_type', 'variety', 'bed__code')
