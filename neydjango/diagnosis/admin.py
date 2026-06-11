from django.contrib import admin
from .models import DiagnosisRequest, DiagnosisImage, DiagnosisResult


class DiagnosisImageInline(admin.TabularInline):
    model = DiagnosisImage
    extra = 0
    readonly_fields = ['image', 'plant_part', 'uploaded_at']


class DiagnosisResultInline(admin.TabularInline):
    model = DiagnosisResult
    extra = 0
    readonly_fields = [
        'disease_label', 'disease_name', 'disease_name_fa',
        'confidence', 'farmer_feedback',
    ]
    fields = readonly_fields


@admin.register(DiagnosisRequest)
class DiagnosisRequestAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'greenhouse', 'submitted_by', 'status',
        'model_version', 'inference_time_ms', 'created_at',
    ]
    list_filter = ['status', 'greenhouse', 'created_at']
    search_fields = ['greenhouse__name', 'submitted_by__username']
    readonly_fields = ['created_at', 'updated_at', 'model_version', 'inference_time_ms']
    inlines = [DiagnosisImageInline, DiagnosisResultInline]
    date_hierarchy = 'created_at'


@admin.register(DiagnosisResult)
class DiagnosisResultAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'request', 'disease_name', 'confidence',
        'farmer_feedback', 'created_at',
    ]
    list_filter = ['farmer_feedback', 'created_at']
    search_fields = ['disease_name', 'disease_label']
