"""
diagnosis/views_template.py

HTML template views for the Disease Detection feature.

Changes from previous version:
  - Saves disease_label (raw) and disease_name (human-readable) separately
  - Calls get_or_create_knowledge() at diagnosis time for each result
  - Stores knowledge snapshot in DiagnosisResult for immutability
  - Calls update_feedback_counts() when farmer submits feedback
"""

import time
import logging

import requests


import os
os.environ['NO_PROXY'] = '127.0.0.1,localhost'


from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from greenhouse_app.models import Greenhouse, Bed, Crop
from accounts.models import GreenhouseMembership

from .models import DiagnosisRequest, DiagnosisImage, DiagnosisResult
from .knowledge import get_or_create_knowledge, update_feedback_counts
from io import BytesIO

logger = logging.getLogger(__name__)
ML_SERVICE_URL = getattr(settings, 'ML_SERVICE_URL', 'http://localhost:8001')


# ── Helper ────────────────────────────────────────────────────────────────────

def _get_greenhouse(request, greenhouse_id):
    return get_object_or_404(
        Greenhouse,
        id=greenhouse_id,
        memberships__user=request.user,
        is_active=True,
    )


def _save_results(diag_request, ml_diagnoses):
    """
    Save ML results to DB, enriching each with knowledge base data.
    Called after a successful ML service response.

    For each diagnosis:
      1. Get or create a DiseaseKnowledge entry (DB cache → OpenAI fallback)
      2. Create DiagnosisResult with both raw ML data and knowledge snapshot
    """
    for diagnosis in ml_diagnoses:
        # Raw ML output — now correctly separated
        raw_label = diagnosis.get('disease_label', '')   # e.g. "Tomato___Leaf_Mold"
        name_en   = diagnosis.get('disease', '')          # e.g. "Tomato Leaf Mold"
        name_fa   = diagnosis.get('disease_fa', '')
        confidence = diagnosis.get('confidence', 0.0)

        # Get or generate knowledge (DB cache → OpenAI → fallback stub)
        knowledge = get_or_create_knowledge(
            label=raw_label,
            name_en=name_en,
            name_fa=name_fa,
        )

        # Create result with knowledge snapshot (immutable copy at time of diagnosis)
        DiagnosisResult.objects.create(
            request=diag_request,
            knowledge=knowledge,
            disease_label=raw_label,
            disease_name=knowledge.name_en,       # use knowledge name (may be better than ML)
            disease_name_fa=knowledge.name_fa,
            confidence=confidence,
            cause=knowledge.cause,
            remedies=knowledge.remedies,
            recommended_pesticides=knowledge.recommended_pesticides,
        )


# ── List ──────────────────────────────────────────────────────────────────────

@login_required
def diagnosis_list(request, greenhouse_id):
    greenhouse = _get_greenhouse(request, greenhouse_id)

    diagnoses = DiagnosisRequest.objects.filter(
        greenhouse=greenhouse,
    ).prefetch_related('images', 'results').order_by('-created_at')

    status_filter = request.GET.get('status', '')
    if status_filter:
        diagnoses = diagnoses.filter(status=status_filter)

    return render(request, 'diagnosis/diagnosis_list.html', {
        'greenhouse': greenhouse,
        'diagnoses': diagnoses,
        'status_filter': status_filter,
        'status_choices': DiagnosisRequest.Status.choices,
        'breadcrumbs': [
            {'label': 'گلخانه‌ها', 'url': '/greenhouse_app/greenhouses/'},
            {'label': greenhouse.name, 'url': f'/greenhouse_app/greenhouses/{greenhouse.id}/'},
            {'label': 'تشخیص بیماری', 'url': None},
        ],
    })


# ── New Diagnosis Form ────────────────────────────────────────────────────────

@login_required
def diagnosis_new(request, greenhouse_id):
    greenhouse = _get_greenhouse(request, greenhouse_id)

    beds = Bed.objects.filter(
        house__greenhouse=greenhouse,
    ).select_related('house').order_by('house__name', 'code')

    active_crops = Crop.objects.filter(
        bed__house__greenhouse=greenhouse,
        status='growing',
    ).order_by('crop_type', 'variety')

    if request.method == 'POST':
        images = request.FILES.getlist('images')

        if not images:
            messages.error(request, 'لطفاً حداقل یک تصویر بارگذاری کنید.')
            return render(request, 'diagnosis/diagnosis_new.html', {
                'greenhouse': greenhouse,
                'beds': beds,
                'active_crops': active_crops,
                'plant_part_choices': DiagnosisImage.PlantPart.choices,
                'breadcrumbs': _new_breadcrumbs(greenhouse),
            })

        if len(images) > 5:
            messages.error(request, 'حداکثر ۵ تصویر برای هر تشخیص.')
            return redirect('diagnosis:diagnosis_new', greenhouse_id=greenhouse.id)

        allowed_types = {'image/jpeg', 'image/png', 'image/webp', 'image/jpg'}
        for img in images:
            if img.content_type not in allowed_types:
                messages.error(request, f'نوع فایل پشتیبانی نمی‌شود: {img.content_type}. از JPEG یا PNG استفاده کنید.')
                return redirect('diagnosis:diagnosis_new', greenhouse_id=greenhouse.id)

        bed_id   = request.POST.get('bed_id') or None
        crop_id  = request.POST.get('crop_id') or None
        plant_part = request.POST.get('plant_part', 'leaf')
        notes    = request.POST.get('notes', '')

        bed  = get_object_or_404(Bed, id=bed_id, house__greenhouse=greenhouse) if bed_id else None
        crop = get_object_or_404(Crop, id=crop_id, bed__house__greenhouse=greenhouse) if crop_id else None

        # Create request record
        diag_request = DiagnosisRequest.objects.create(
            submitted_by=request.user,
            greenhouse=greenhouse,
            bed=bed,
            crop=crop,
            notes=notes,
            status=DiagnosisRequest.Status.PROCESSING,
        )

        # Save images to disk
        for img_file in images:
            DiagnosisImage.objects.create(
                request=diag_request,
                image=img_file,
                plant_part=plant_part,
            )

        # Call ML service
        start_ms = int(time.time() * 1000)
        image_files = []
        for diag_image in diag_request.images.all():
            try:
                diag_image.image.open('rb')
                image_bytes = diag_image.image.read()
                diag_image.image.close()
                image_files.append((
                    'images',
                    (diag_image.image.name, BytesIO(image_bytes), 'image/jpeg')
                ))
            except Exception as e:
                logger.error(f'Cannot open saved image: {e}')

        try:
            ml_response = requests.post(
                f'{ML_SERVICE_URL}/predict',
                files=image_files,
                timeout=30,
                proxies={'http': None, 'https': None},  # bypass proxy for ML service
            )
            ml_response.raise_for_status()
            ml_data = ml_response.json()

        except requests.exceptions.ConnectionError:
            diag_request.status = DiagnosisRequest.Status.FAILED
            diag_request.ml_error = 'ML service is not running on localhost:8001.'
            diag_request.save()
            messages.error(request, 'Disease detection service is offline. Start the ML service and try again.')
            return redirect('diagnosis:diagnosis_list', greenhouse_id=greenhouse.id)

        except requests.exceptions.Timeout:
            diag_request.status = DiagnosisRequest.Status.FAILED
            diag_request.ml_error = 'ML service timed out.'
            diag_request.save()
            messages.error(request, 'Disease detection timed out. Please try again.')
            return redirect('diagnosis:diagnosis_list', greenhouse_id=greenhouse.id)

        except Exception as e:
            import traceback
            logger.error(f'Full error: {traceback.format_exc()}')
            diag_request.status = DiagnosisRequest.Status.FAILED
            diag_request.ml_error = str(e)
            diag_request.save()
            messages.error(request, f'An error occurred: {e}')
            return redirect('diagnosis:diagnosis_list', greenhouse_id=greenhouse.id)

        finally:
            for _, (_, file_obj, _) in image_files:
                try:
                    file_obj.close()
                except Exception:
                    pass

        elapsed_ms = int(time.time() * 1000) - start_ms

        # Save results with knowledge enrichment
        _save_results(diag_request, ml_data.get('diagnoses', []))

        diag_request.status = DiagnosisRequest.Status.COMPLETED
        diag_request.model_version = ml_data.get('model_version', '')
        diag_request.inference_time_ms = elapsed_ms
        diag_request.save()

        messages.success(request, 'Diagnosis completed.')
        return redirect('diagnosis:diagnosis_detail', greenhouse_id=greenhouse.id, pk=diag_request.id)

    return render(request, 'diagnosis/diagnosis_new.html', {
        'greenhouse': greenhouse,
        'beds': beds,
        'active_crops': active_crops,
        'plant_part_choices': DiagnosisImage.PlantPart.choices,
        'breadcrumbs': _new_breadcrumbs(greenhouse),
    })


# ── Detail ────────────────────────────────────────────────────────────────────

@login_required
def diagnosis_detail(request, greenhouse_id, pk):
    greenhouse = _get_greenhouse(request, greenhouse_id)
    diag_request = get_object_or_404(
        DiagnosisRequest,
        id=pk,
        greenhouse=greenhouse,
    )

    if request.method == 'POST':
        result_id    = request.POST.get('result_id')
        feedback     = request.POST.get('farmer_feedback')
        farmer_notes = request.POST.get('farmer_notes', '')

        if result_id and feedback:
            result = get_object_or_404(DiagnosisResult, id=result_id, request=diag_request)
            was_pending = result.farmer_feedback == DiagnosisResult.FarmerFeedback.PENDING

            result.farmer_feedback = feedback
            result.farmer_notes = farmer_notes
            result.save()

            # Update knowledge base accuracy counters
            if was_pending and result.disease_label:
                update_feedback_counts(
                    label=result.disease_label,
                    confirmed=(feedback == 'confirmed'),
                )

            messages.success(request, 'Feedback saved — thank you for improving the system.')

        return redirect('diagnosis:diagnosis_detail', greenhouse_id=greenhouse.id, pk=pk)

    return render(request, 'diagnosis/diagnosis_detail.html', {
        'greenhouse': greenhouse,
        'diag_request': diag_request,
        'results': diag_request.results.order_by('-confidence'),
        'images': diag_request.images.all(),
        'breadcrumbs': [
            {'label': 'گلخانه‌ها', 'url': '/greenhouse_app/greenhouses/'},
            {'label': greenhouse.name, 'url': f'/greenhouse_app/greenhouses/{greenhouse.id}/'},
            {'label': 'تشخیص بیماری', 'url': f'/greenhouse_app/greenhouses/{greenhouse.id}/diagnosis/'},
            {'label': f'تشخیص #{diag_request.id}', 'url': None},
        ],
    })


# ── Breadcrumb helpers ────────────────────────────────────────────────────────

def _new_breadcrumbs(greenhouse):
    return [
        {'label': 'گلخانه‌ها', 'url': '/greenhouse_app/greenhouses/'},
        {'label': greenhouse.name, 'url': f'/greenhouse_app/greenhouses/{greenhouse.id}/'},
        {'label': 'تشخیص بیماری', 'url': f'/greenhouse_app/greenhouses/{greenhouse.id}/diagnosis/'},
        {'label': 'تشخیص جدید', 'url': None},
    ]


