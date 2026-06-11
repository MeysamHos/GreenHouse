"""
diagnosis/views.py

Django REST Framework views for disease detection.

POST /api/v1/diagnose/
  - Receives images + metadata from the mobile app or browser
  - Saves images to disk
  - Calls FastAPI ML service at localhost:8001/predict
  - Saves results to DB
  - Returns the document's exact response format

GET  /api/v1/diagnose/
  - Lists past diagnosis requests for the authenticated user's greenhouses

GET  /api/v1/diagnose/<id>/
  - Returns full detail of one diagnosis request

PATCH /api/v1/diagnose/<id>/results/<result_id>/feedback/
  - Farmer confirms or rejects a diagnosis (feedback loop for ML retraining)
"""

import time
import logging

import requests
from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import GreenhouseMembership
from greenhouse_app.models import Greenhouse, Bed, Crop

from .models import DiagnosisRequest, DiagnosisImage, DiagnosisResult
from .serializers import (
    DiagnosisRequestSerializer,
    DiagnosisRequestListSerializer,
    FeedbackSerializer,
)

logger = logging.getLogger(__name__)

ML_SERVICE_URL = getattr(settings, 'ML_SERVICE_URL', 'http://localhost:8001')


# ── Helper ────────────────────────────────────────────────────────────────────

def _get_greenhouse_or_403(request, greenhouse_id):
    """Return greenhouse if authenticated user is a member, else raise."""
    from rest_framework.exceptions import PermissionDenied, NotFound
    try:
        gh = Greenhouse.objects.get(id=greenhouse_id, is_active=True)
    except Greenhouse.DoesNotExist:
        raise NotFound('Greenhouse not found.')
    if not GreenhouseMembership.objects.filter(greenhouse=gh, user=request.user).exists():
        raise PermissionDenied('You are not a member of this greenhouse.')
    return gh


# ── POST /api/v1/diagnose/ ────────────────────────────────────────────────────

class DiagnoseView(APIView):
    """
    POST /api/v1/diagnose/
    Accepts multipart/form-data:
      images[]       — one to five image files (required)
      greenhouse_id  — int (required)
      bed_id         — int (optional)
      crop_id        — int (optional)
      notes          — string (optional)
      plant_part     — leaf|stem|fruit|root|whole|other (optional, default: leaf)

    Returns the document's exact response format:
      {
        "id": 1,
        "diagnoses": [
          {
            "disease": "Tomato Early Blight",
            "disease_fa": "بلایت اولیه گوجه‌فرنگی",
            "confidence": 0.94,
            "cause": "...",
            "remedies": [...],
            "recommended_pesticides": [...]
          }
        ],
        "model_version": "mobilenetv2-plantvillage-v1",
        "images_processed": 2,
        "status": "completed"
      }
    """
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # ── Validate inputs ───────────────────────────────────────────
        greenhouse_id = request.data.get('greenhouse_id')
        if not greenhouse_id:
            return Response(
                {'detail': 'greenhouse_id is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        images = request.FILES.getlist('images')
        if not images:
            return Response(
                {'detail': 'At least one image is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if len(images) > 5:
            return Response(
                {'detail': 'Maximum 5 images per request.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate file types
        allowed_types = {'image/jpeg', 'image/png', 'image/webp', 'image/jpg'}
        for img in images:
            if img.content_type not in allowed_types:
                return Response(
                    {'detail': f'Unsupported file type: {img.content_type}. Use JPEG or PNG.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # ── Verify membership ─────────────────────────────────────────
        greenhouse = _get_greenhouse_or_403(request, greenhouse_id)

        # Optional foreign keys
        bed_id = request.data.get('bed_id')
        crop_id = request.data.get('crop_id')
        bed = get_object_or_404(Bed, id=bed_id, house__greenhouse=greenhouse) if bed_id else None
        crop = get_object_or_404(Crop, id=crop_id, bed__house__greenhouse=greenhouse) if crop_id else None

        plant_part = request.data.get('plant_part', 'leaf')
        notes = request.data.get('notes', '')

        # ── Create the request record ─────────────────────────────────
        diag_request = DiagnosisRequest.objects.create(
            submitted_by=request.user,
            greenhouse=greenhouse,
            bed=bed,
            crop=crop,
            notes=notes,
            status=DiagnosisRequest.Status.PROCESSING,
        )

        # ── Save images to disk ───────────────────────────────────────
        for img_file in images:
            DiagnosisImage.objects.create(
                request=diag_request,
                image=img_file,
                plant_part=plant_part,
            )

        # ── Call FastAPI ML service ───────────────────────────────────
        start_ms = int(time.time() * 1000)

        # Re-read saved images from disk to send to ML service
        # (Files have already been consumed by Django's upload handler)
        image_files = []
        for diag_image in diag_request.images.all():
            try:
                f = diag_image.image.open('rb')
                image_files.append(
                    ('images', (diag_image.image.name, f, 'image/jpeg'))
                )
            except Exception as e:
                logger.error(f"Cannot open saved image: {e}")

        try:
            ml_response = requests.post(
                f'{ML_SERVICE_URL}/predict',
                files=image_files,
                timeout=30,
            )
            ml_response.raise_for_status()
            ml_data = ml_response.json()

        except requests.exceptions.ConnectionError:
            diag_request.status = DiagnosisRequest.Status.FAILED
            diag_request.ml_error = (
                'ML service is not running. Start it with: '
                'cd ml_service && uvicorn main:app --port 8001'
            )
            diag_request.save()
            return Response(
                {'detail': diag_request.ml_error},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        except requests.exceptions.Timeout:
            diag_request.status = DiagnosisRequest.Status.FAILED
            diag_request.ml_error = 'ML service timed out after 30 seconds.'
            diag_request.save()
            return Response(
                {'detail': diag_request.ml_error},
                status=status.HTTP_504_GATEWAY_TIMEOUT
            )
        except requests.exceptions.HTTPError as e:
            diag_request.status = DiagnosisRequest.Status.FAILED
            diag_request.ml_error = f'ML service error: {str(e)}'
            diag_request.save()
            return Response(
                {'detail': diag_request.ml_error},
                status=status.HTTP_502_BAD_GATEWAY
            )
        finally:
            # Close all file handles
            for _, (_, f, _) in image_files:
                try:
                    f.close()
                except Exception:
                    pass

        elapsed_ms = int(time.time() * 1000) - start_ms

        # ── Save ML results to DB ─────────────────────────────────────
        for diagnosis in ml_data.get('diagnoses', []):
            DiagnosisResult.objects.create(
                request=diag_request,
                disease_label=diagnosis.get('disease', ''),
                disease_name=diagnosis.get('disease', ''),
                disease_name_fa=diagnosis.get('disease_fa', ''),
                confidence=diagnosis.get('confidence', 0.0),
                cause=diagnosis.get('cause', ''),
                remedies=diagnosis.get('remedies', []),
                recommended_pesticides=diagnosis.get('recommended_pesticides', []),
            )

        # ── Update request status ─────────────────────────────────────
        diag_request.status = DiagnosisRequest.Status.COMPLETED
        diag_request.model_version = ml_data.get('model_version', '')
        diag_request.inference_time_ms = elapsed_ms
        diag_request.save()

        # ── Build response matching document spec ─────────────────────
        serializer = DiagnosisRequestSerializer(diag_request)
        response_data = serializer.data
        response_data['images_processed'] = ml_data.get('images_processed', len(images))

        return Response(response_data, status=status.HTTP_201_CREATED)


# ── GET /api/v1/diagnose/ ─────────────────────────────────────────────────────

class DiagnoseListView(APIView):
    """
    GET /api/v1/diagnose/?greenhouse_id=<id>
    Lists past diagnosis requests for a greenhouse.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        greenhouse_id = request.query_params.get('greenhouse_id')
        if not greenhouse_id:
            return Response(
                {'detail': 'greenhouse_id query parameter is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        greenhouse = _get_greenhouse_or_403(request, greenhouse_id)

        qs = DiagnosisRequest.objects.filter(
            greenhouse=greenhouse
        ).prefetch_related('images', 'results').order_by('-created_at')

        # Optional filters
        bed_id = request.query_params.get('bed_id')
        if bed_id:
            qs = qs.filter(bed_id=bed_id)

        status_filter = request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)

        serializer = DiagnosisRequestListSerializer(qs, many=True)
        return Response({'count': qs.count(), 'results': serializer.data})


# ── GET /api/v1/diagnose/<id>/ ────────────────────────────────────────────────

class DiagnoseDetailView(APIView):
    """
    GET /api/v1/diagnose/<id>/
    Full detail of one diagnosis request.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        diag_request = get_object_or_404(DiagnosisRequest, id=pk)
        _get_greenhouse_or_403(request, diag_request.greenhouse_id)
        serializer = DiagnosisRequestSerializer(diag_request)
        return Response(serializer.data)


# ── PATCH /api/v1/diagnose/<id>/results/<result_id>/feedback/ ─────────────────

class DiagnosisFeedbackView(APIView):
    """
    PATCH /api/v1/diagnose/<id>/results/<result_id>/feedback/

    Farmer confirms or rejects a diagnosis result.
    This data is used to improve the ML model over time.

    Body:
      {
        "farmer_feedback": "confirmed" | "rejected",
        "farmer_notes": "Actually this was late blight, not early blight"
      }
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk, result_id):
        diag_request = get_object_or_404(DiagnosisRequest, id=pk)
        _get_greenhouse_or_403(request, diag_request.greenhouse_id)

        result = get_object_or_404(DiagnosisResult, id=result_id, request=diag_request)

        serializer = FeedbackSerializer(result, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
