"""
operations/admin.py
"""

from django.contrib import admin
from .models import Operation, OperationPhoto, CropOperationTemplate, CropOperationTemplateStep


class OperationPhotoInline(admin.TabularInline):
    model = OperationPhoto
    extra = 0
    readonly_fields = ('uploaded_at',)


@admin.register(Operation)
class OperationAdmin(admin.ModelAdmin):
    list_display = (
        'operation_type', 'bed', 'performed_at',
        'performed_by', 'quantity', 'unit', 'cost',
    )
    list_filter  = ('operation_type', 'performed_at')
    search_fields = (
        'bed__code', 'bed__house__name',
        'bed__house__greenhouse__name',
        'product_name', 'notes',
    )
    date_hierarchy = 'performed_at'
    inlines = [OperationPhotoInline]
    raw_id_fields = ('bed', 'crop', 'performed_by', 'logged_by')


@admin.register(OperationPhoto)
class OperationPhotoAdmin(admin.ModelAdmin):
    list_display = ('operation', 'caption', 'uploaded_at')
    raw_id_fields = ('operation',)



class CropOperationTemplateStepInline(admin.TabularInline):
    """
    Lets you enter all steps for a template directly on the template's
    admin page, one row per step — matching the existing HouseInline /
    BedInline / CropInline pattern already used in greenhouse_app/admin.py.

    Each row covers both one-off steps (repeat_every_days left blank) and
    recurring steps (repeat_every_days + repeat_until_day filled in) —
    no separate UI needed for the two cases, they're just different field
    values on the same row, kept visible together as your earlier decision
    required ("keep each step as one inline row with all repeat fields
    visible in that row").
    """
    model = CropOperationTemplateStep
    extra = 1
    fields = (
        'operation_type',
        'day_offset_start',
        'repeat_every_days',
        'repeat_until_day',
        'quantity',
        'unit',
        'product_name',
        'notes',
    )
    ordering = ('day_offset_start',)


@admin.register(CropOperationTemplate)
class CropOperationTemplateAdmin(admin.ModelAdmin):
    list_display = (
        'crop_type', 'variety', 'name', 'greenhouse_scope_label',
        'is_active', 'step_count', 'created_at',
    )
    list_filter = ('is_active', 'crop_type', 'greenhouse')
    search_fields = ('crop_type', 'variety', 'name', 'greenhouse__name')
    inlines = [CropOperationTemplateStepInline]
    # `greenhouse` left as a normal dropdown (not raw_id_fields) — unlike
    # Operation's bed/crop/performed_by/logged_by, the number of
    # greenhouses per install is small, so a select widget stays usable.

    def greenhouse_scope_label(self, obj):
        return obj.greenhouse.name if obj.greenhouse_id else 'سراسری (Global)'
    greenhouse_scope_label.short_description = 'محدوده'

    def step_count(self, obj):
        return obj.steps.count()
    step_count.short_description = 'تعداد مراحل'
