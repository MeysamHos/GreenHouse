from django.contrib import admin
from .models import Sale, Expense


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ['id', 'greenhouse', 'product_name', 'buyer_name', 'quantity_kg',
                    'price_per_kg', 'payment_status', 'sold_at']
    list_filter = ['payment_status', 'sold_at', 'greenhouse']
    search_fields = ['buyer_name', 'product_name', 'invoice_number']
    date_hierarchy = 'sold_at'
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ['id', 'greenhouse', 'category', 'description', 'amount',
                    'vendor_name', 'expense_date']
    list_filter = ['category', 'expense_date', 'greenhouse']
    search_fields = ['description', 'vendor_name', 'invoice_number']
    date_hierarchy = 'expense_date'
    readonly_fields = ['created_at', 'updated_at']
