"""
financials/serializers.py

DRF serializers for Sale, Expense, and the computed P&L report.
"""

from decimal import Decimal
from rest_framework import serializers
from .models import Sale, Expense


class SaleSerializer(serializers.ModelSerializer):
    total_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    amount_outstanding = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    crop_name = serializers.SerializerMethodField()

    class Meta:
        model = Sale
        fields = [
            'id', 'greenhouse', 'crop', 'crop_name',
            'buyer_name', 'buyer_phone',
            'product_name', 'quantity_kg', 'price_per_kg',
            'total_amount', 'payment_status', 'amount_paid', 'amount_outstanding',
            'invoice_number', 'sold_at', 'notes',
            'recorded_by', 'created_at',
        ]
        read_only_fields = ['id', 'recorded_by', 'created_at']

    def get_crop_name(self, obj):
        if obj.crop:
            return f'{obj.crop.crop_type} — {obj.crop.variety}'
        return None

    def create(self, validated_data):
        validated_data['recorded_by'] = self.context['request'].user
        return super().create(validated_data)


class ExpenseSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(
        source='get_category_display', read_only=True
    )
    house_name = serializers.SerializerMethodField()

    class Meta:
        model = Expense
        fields = [
            'id', 'greenhouse', 'category', 'category_display',
            'description', 'amount', 'house', 'house_name',
            'expense_date', 'invoice_number', 'vendor_name', 'notes',
            'recorded_by', 'created_at',
        ]
        read_only_fields = ['id', 'recorded_by', 'created_at']

    def get_house_name(self, obj):
        return obj.house.name if obj.house else None

    def create(self, validated_data):
        validated_data['recorded_by'] = self.context['request'].user
        return super().create(validated_data)


class PnLReportSerializer(serializers.Serializer):
    """
    Read-only serializer for the computed P&L report.
    This is never written to DB — always computed on demand.
    """
    period_from = serializers.DateField()
    period_to = serializers.DateField()
    greenhouse_id = serializers.IntegerField()
    greenhouse_name = serializers.CharField()

    # Revenue
    total_revenue = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_sales_count = serializers.IntegerField()

    # Costs — broken down by source
    cost_operations = serializers.DecimalField(max_digits=14, decimal_places=2)
    cost_purchases = serializers.DecimalField(max_digits=14, decimal_places=2)
    cost_expenses = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_cost = serializers.DecimalField(max_digits=14, decimal_places=2)

    # Bottom line
    gross_profit = serializers.DecimalField(max_digits=14, decimal_places=2)
    profit_margin_pct = serializers.DecimalField(max_digits=6, decimal_places=2)

    # Breakdowns
    expense_by_category = serializers.DictField(child=serializers.DecimalField(
        max_digits=12, decimal_places=2
    ))
    top_crops_by_revenue = serializers.ListField(child=serializers.DictField())
