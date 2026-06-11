"""
operations/serializers.py
"""

from rest_framework import serializers
from accounts.serializers import UserMinimalSerializer
from .models import Operation, OperationPhoto


class OperationPhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = OperationPhoto
        fields = ['id', 'image', 'caption', 'uploaded_at']
        read_only_fields = ['id', 'uploaded_at']


class OperationListSerializer(serializers.ModelSerializer):
    """Compact — for list views and embedding in bed/crop detail."""
    performed_by = UserMinimalSerializer(read_only=True)
    operation_type_display = serializers.CharField(
        source='get_operation_type_display', read_only=True
    )
    bed_code = serializers.CharField(source='bed.code', read_only=True)

    class Meta:
        model = Operation
        fields = [
            'id', 'operation_type', 'operation_type_display',
            'performed_at', 'bed_code',
            'quantity', 'unit', 'product_name',
            'cost', 'harvest_weight_kg',
            'performed_by',
        ]


class OperationDetailSerializer(serializers.ModelSerializer):
    """Full detail — for retrieve, create, update."""
    performed_by = UserMinimalSerializer(read_only=True)
    logged_by    = UserMinimalSerializer(read_only=True)
    photos       = OperationPhotoSerializer(many=True, read_only=True)
    operation_type_display = serializers.CharField(
        source='get_operation_type_display', read_only=True
    )

    class Meta:
        model = Operation
        fields = [
            'id',
            'bed', 'crop',
            'operation_type', 'operation_type_display',
            'performed_at',
            'quantity', 'unit',
            'product_name', 'product_batch',
            'cost',
            'harvest_weight_kg', 'harvest_quality',
            'notes',
            'performed_by', 'logged_by',
            'photos',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'logged_by', 'created_at', 'updated_at']

    def create(self, validated_data):
        validated_data['logged_by'] = self.context['request'].user
        return super().create(validated_data)


class OperationWriteSerializer(serializers.ModelSerializer):
    """Write serializer — excludes read-only computed fields."""

    class Meta:
        model = Operation
        fields = [
            'bed', 'crop',
            'operation_type',
            'performed_at',
            'quantity', 'unit',
            'product_name', 'product_batch',
            'cost',
            'harvest_weight_kg', 'harvest_quality',
            'notes',
            'performed_by',
        ]

    def create(self, validated_data):
        validated_data['logged_by'] = self.context['request'].user
        return super().create(validated_data)

    def validate(self, attrs):
        # Harvest weight only makes sense for harvesting operations
        if attrs.get('harvest_weight_kg') and attrs.get('operation_type') != 'harvesting':
            raise serializers.ValidationError(
                {'harvest_weight_kg': 'Harvest weight can only be set for harvesting operations.'}
            )
        return attrs
