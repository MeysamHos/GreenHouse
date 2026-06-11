"""
diagnosis/serializers.py
"""

from rest_framework import serializers
from .models import DiagnosisRequest, DiagnosisImage, DiagnosisResult


class DiagnosisImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = DiagnosisImage
        fields = ['id', 'image', 'plant_part', 'uploaded_at']
        read_only_fields = ['id', 'uploaded_at']


class DiagnosisResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = DiagnosisResult
        fields = [
            'id',
            'disease_label',
            'disease',         # mapped below
            'disease_fa',      # mapped below
            'confidence',
            'cause',
            'remedies',
            'recommended_pesticides',
            'farmer_feedback',
            'farmer_notes',
        ]
        read_only_fields = ['id', 'disease_label', 'confidence', 'cause',
                            'remedies', 'recommended_pesticides']

    # Rename fields to match the document's response spec
    disease = serializers.CharField(source='disease_name', read_only=True)
    disease_fa = serializers.CharField(source='disease_name_fa', read_only=True)


class DiagnosisRequestSerializer(serializers.ModelSerializer):
    """Full detail — returned after diagnosis completes."""
    images = DiagnosisImageSerializer(many=True, read_only=True)
    diagnoses = DiagnosisResultSerializer(source='results', many=True, read_only=True)
    submitted_by_username = serializers.CharField(
        source='submitted_by.username', read_only=True
    )

    class Meta:
        model = DiagnosisRequest
        fields = [
            'id',
            'greenhouse',
            'bed',
            'crop',
            'status',
            'model_version',
            'inference_time_ms',
            'notes',
            'submitted_by_username',
            'images',
            'diagnoses',          # matches document response spec
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id', 'status', 'model_version', 'inference_time_ms',
            'submitted_by_username', 'images', 'diagnoses',
            'created_at', 'updated_at',
        ]


class DiagnosisRequestListSerializer(serializers.ModelSerializer):
    """Compact — for list views."""
    top_diagnosis = serializers.SerializerMethodField()
    image_count = serializers.IntegerField(source='images.count', read_only=True)

    class Meta:
        model = DiagnosisRequest
        fields = [
            'id', 'greenhouse', 'bed', 'crop',
            'status', 'model_version',
            'image_count', 'top_diagnosis',
            'created_at',
        ]

    def get_top_diagnosis(self, obj):
        result = obj.results.order_by('-confidence').first()
        if result:
            return {
                'disease': result.disease_name,
                'confidence': result.confidence,
            }
        return None


class FeedbackSerializer(serializers.ModelSerializer):
    """Used for PATCH /diagnoses/<request_id>/results/<result_id>/feedback/"""
    class Meta:
        model = DiagnosisResult
        fields = ['farmer_feedback', 'farmer_notes']
