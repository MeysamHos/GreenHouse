"""
inventory/serializers.py
"""

from rest_framework import serializers
from .models import InventoryItem, InventoryTransaction


class InventoryTransactionSerializer(serializers.ModelSerializer):
    transaction_type_display = serializers.CharField(
        source='get_transaction_type_display', read_only=True
    )
    total_cost = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )

    class Meta:
        model = InventoryTransaction
        fields = [
            'id', 'item', 'transaction_type', 'transaction_type_display',
            'quantity', 'unit_price', 'total_cost',
            'operation', 'supplier_name', 'invoice_number',
            'batch_number', 'expiry_date',
            'notes', 'performed_at', 'recorded_by',
            'created_at',
        ]
        read_only_fields = ['id', 'recorded_by', 'created_at']

    def create(self, validated_data):
        validated_data['recorded_by'] = self.context['request'].user
        return super().create(validated_data)


class InventoryItemListSerializer(serializers.ModelSerializer):
    """Compact — for list views."""
    category_display = serializers.CharField(
        source='get_category_display', read_only=True
    )
    unit_display = serializers.CharField(
        source='get_unit_display', read_only=True
    )
    current_stock = serializers.SerializerMethodField()
    is_low_stock  = serializers.BooleanField(read_only=True)

    class Meta:
        model = InventoryItem
        fields = [
            'id', 'name', 'category', 'category_display',
            'unit', 'unit_display', 'brand',
            'current_stock', 'min_stock_threshold', 'is_low_stock',
            'unit_cost', 'is_active',
        ]

    def get_current_stock(self, obj):
        return obj.current_stock()


class InventoryItemDetailSerializer(serializers.ModelSerializer):
    """Full detail — includes recent transactions."""
    category_display = serializers.CharField(
        source='get_category_display', read_only=True
    )
    unit_display = serializers.CharField(
        source='get_unit_display', read_only=True
    )
    current_stock  = serializers.SerializerMethodField()
    is_low_stock   = serializers.BooleanField(read_only=True)
    recent_transactions = serializers.SerializerMethodField()

    class Meta:
        model = InventoryItem
        fields = [
            'id', 'greenhouse', 'name', 'category', 'category_display',
            'unit', 'unit_display', 'brand', 'description',
            'current_stock', 'min_stock_threshold', 'is_low_stock',
            'unit_cost', 'is_active',
            'recent_transactions',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_current_stock(self, obj):
        return obj.current_stock()

    def get_recent_transactions(self, obj):
        recent = obj.transactions.order_by('-performed_at')[:10]
        return InventoryTransactionSerializer(recent, many=True).data

    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)
