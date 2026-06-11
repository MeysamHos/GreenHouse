"""
operations/admin.py
"""

from django.contrib import admin
from .models import Operation, OperationPhoto


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
