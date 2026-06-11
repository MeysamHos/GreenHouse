"""
diagnosis/models.py

Stores disease detection requests and their results.

Design:
  - DiagnosisRequest  → one diagnosis session (user uploads images for a bed/crop)
  - DiagnosisImage    → each uploaded image attached to a request
  - DiagnosisResult   → each disease found (one request can surface multiple diseases)

This gives a full audit trail:
  - What images were submitted
  - What the ML model returned
  - Which version of the model was used
  - Whether the farmer confirmed or rejected the result (feedback loop)

The feedback loop (confirmed/rejected) is critical for future model fine-tuning.
"""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class DiagnosisRequest(models.Model):
    """
    One disease detection session.
    A farmer uploads 1-5 images of a plant showing symptoms.
    The ML service analyses them and returns diagnoses.
    """

    class Status(models.TextChoices):
        PENDING    = 'pending',    _('Pending')      # images received, waiting for ML
        PROCESSING = 'processing', _('Processing')   # ML service running
        COMPLETED  = 'completed',  _('Completed')    # results ready
        FAILED     = 'failed',     _('Failed')       # ML service error

    # Who submitted this request
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='diagnosis_requests',
    )

    # Where the photos were taken
    greenhouse = models.ForeignKey(
        'greenhouse_app.Greenhouse',
        on_delete=models.CASCADE,
        related_name='diagnosis_requests',
    )
    bed = models.ForeignKey(
        'greenhouse_app.Bed',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='diagnosis_requests',
        help_text=_('Specific bed the photos were taken from'),
    )
    crop = models.ForeignKey(
        'greenhouse_app.Crop',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='diagnosis_requests',
        help_text=_('Active crop at the time of diagnosis'),
    )

    # Processing state
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )

    # ML service metadata
    model_version = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text=_('Version of the ML model that processed this request'),
    )
    ml_error = models.TextField(
        blank=True,
        default='',
        help_text=_('Error message if ML service failed'),
    )
    inference_time_ms = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=_('Time taken by ML service in milliseconds'),
    )

    # Free text notes from the farmer
    notes = models.TextField(
        blank=True,
        default='',
        help_text=_('Farmer observations about the symptoms'),
    )

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'diagnosis_requests'
        verbose_name = _('Diagnosis Request')
        verbose_name_plural = _('Diagnosis Requests')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['greenhouse', 'created_at']),
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        return f'Diagnosis #{self.id} — {self.greenhouse.name} ({self.status})'


class DiagnosisImage(models.Model):
    """
    A single image uploaded as part of a diagnosis request.
    Stored permanently for audit trail and future model training.
    """

    class PlantPart(models.TextChoices):
        LEAF    = 'leaf',    _('Leaf')
        STEM    = 'stem',    _('Stem')
        FRUIT   = 'fruit',   _('Fruit')
        ROOT    = 'root',    _('Root')
        WHOLE   = 'whole',   _('Whole plant')
        OTHER   = 'other',   _('Other')

    request = models.ForeignKey(
        DiagnosisRequest,
        on_delete=models.CASCADE,
        related_name='images',
    )
    image = models.ImageField(
        upload_to='diagnosis/images/%Y/%m/',
        help_text=_('Uploaded plant photo'),
    )
    plant_part = models.CharField(
        max_length=20,
        choices=PlantPart.choices,
        default=PlantPart.LEAF,
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'diagnosis_images'
        verbose_name = _('Diagnosis Image')
        verbose_name_plural = _('Diagnosis Images')

    def __str__(self):
        return f'Image #{self.id} for request #{self.request_id}'


class DiagnosisResult(models.Model):
    """
    One disease identified in a diagnosis request.
    A single request can have multiple results (e.g. both early blight and
    spider mites detected with different confidence levels).
    """

    class FarmerFeedback(models.TextChoices):
        PENDING   = 'pending',   _('Not yet reviewed')
        CONFIRMED = 'confirmed', _('Farmer confirmed this diagnosis')
        REJECTED  = 'rejected',  _('Farmer rejected this diagnosis')

    request = models.ForeignKey(
        DiagnosisRequest,
        on_delete=models.CASCADE,
        related_name='results',
    )

    # ML model output
    disease_label = models.CharField(
        max_length=200,
        help_text=_('Raw PlantVillage label, e.g. Tomato___Early_blight'),
    )
    disease_name = models.CharField(
        max_length=200,
        help_text=_('Human-readable English name'),
    )
    disease_name_fa = models.CharField(
        max_length=200,
        blank=True,
        default='',
        help_text=_('Human-readable Farsi name'),
    )
    confidence = models.FloatField(
        help_text=_('Model confidence 0.0-1.0'),
    )

    # Enriched knowledge base data (stored as text for immutability)
    cause = models.TextField(blank=True, default='')
    remedies = models.JSONField(
        default=list,
        help_text=_('List of treatment recommendations'),
    )
    recommended_pesticides = models.JSONField(
        default=list,
        help_text=_('List of pesticides with name, active_ingredient, dose'),
    )

    # Farmer feedback — critical for model improvement
    farmer_feedback = models.CharField(
        max_length=20,
        choices=FarmerFeedback.choices,
        default=FarmerFeedback.PENDING,
        db_index=True,
    )
    farmer_notes = models.TextField(
        blank=True,
        default='',
        help_text=_('What the farmer says was actually wrong'),
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'diagnosis_results'
        verbose_name = _('Diagnosis Result')
        verbose_name_plural = _('Diagnosis Results')
        ordering = ['-confidence']

    def __str__(self):
        return f'{self.disease_name} ({self.confidence:.0%}) for request #{self.request_id}'
