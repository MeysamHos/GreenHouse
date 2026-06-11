"""
inventory/admin.py
"""

from django.contrib import admin
from .models import InventoryItem, InventoryTransaction


class InventoryTransactionInline(admin.TabularInline):
    model = InventoryTransaction
    extra = 0
    readonly_fields = ('recorded_by', 'created_at', 'total_cost')
    fields = (
        'transaction_type', 'quantity', 'unit_price', 'total_cost',
        'performed_at', 'supplier_name', 'recorded_by',
    )


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'category', 'unit', 'brand',
        'min_stock_threshold', 'unit_cost', 'is_active',
    )
    list_filter  = ('category', 'is_active', 'greenhouse')
    search_fields = ('name', 'brand', 'description')
    inlines = [InventoryTransactionInline]
    raw_id_fields = ('greenhouse', 'created_by')


@admin.register(InventoryTransaction)
class InventoryTransactionAdmin(admin.ModelAdmin):
    list_display = (
        'item', 'transaction_type', 'quantity',
        'unit_price', 'performed_at', 'recorded_by',
    )
    list_filter  = ('transaction_type', 'performed_at')
    search_fields = ('item__name', 'supplier_name', 'invoice_number', 'batch_number')
    date_hierarchy = 'performed_at'
    raw_id_fields  = ('item', 'operation', 'recorded_by')
