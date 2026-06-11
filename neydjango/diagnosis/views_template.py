"""
diagnosis/views_template.py

HTML template views for the Disease Detection feature.
Separate from views.py (DRF/JSON) — same pattern as other apps.

Three pages:
  1. diagnosis_list  — past diagnoses for a greenhouse
  2. diagnosis_new   — upload form (submits to the DRF API view, then redirects to result)
  3. diagnosis_detail — shows one completed diagnosis with results
"""

import time
import logging

import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from greenhouse_app.models import Greenhouse, Bed, Crop
from accounts.models import GreenhouseMembership

from .models import DiagnosisRequest, DiagnosisImage, DiagnosisResult

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


# ── List ──────────────────────────────────────────────────────────────────────

@login_required
def diagnosis_list(request, greenhouse_id):
    greenhouse = _get_greenhouse(request, greenhouse_id)

    diagnoses = DiagnosisRequest.objects.filter(
        greenhouse=greenhouse,
    ).prefetch_related('images', 'results').order_by('-created_at')

    # Simple filters
    status_filter = request.GET.get('status', '')
    if status_filter:
        diagnoses = diagnoses.filter(status=status_filter)

    return render(request, 'diagnosis/diagnosis_list.html', {
        'greenhouse': greenhouse,
        'diagnoses': diagnoses,
        'status_filter': status_filter,
        'status_choices': DiagnosisRequest.Status.choices,
        'breadcrumbs': [
            {'label': 'Greenhouses', 'url': '/greenhouse_app/greenhouses/'},
            {'label': greenhouse.name, 'url': f'/greenhouse_app/greenhouses/{greenhouse.id}/'},
            {'label': 'Disease Detection', 'url': None},
        ],
    })


# ── New Diagnosis Form ────────────────────────────────────────────────────────

@login_required
def diagnosis_new(request, greenhouse_id):
    greenhouse = _get_greenhouse(request, greenhouse_id)

    # Dropdowns for the form
    beds = Bed.objects.filter(
        house__greenhouse=greenhouse,
    ).select_related('house').order_by('house__name', 'code')

    active_crops = Crop.objects.filter(
        bed__house__greenhouse=greenhouse,
        status='growing',
    ).order_by('crop_type', 'variety')

    if request.method == 'POST':
        images = request.FILES.getlist('images')

        # Client-side validation replicated server-side
        if not images:
            messages.error(request, 'Please upload at least one image.')
            return render(request, 'diagnosis/diagnosis_new.html', {
                'greenhouse': greenhouse,
                'beds': beds,
                'active_crops': active_crops,
                'plant_part_choices': DiagnosisImage.PlantPart.choices,
                'breadcrumbs': [
                    {'label': 'Greenhouses', 'url': '/greenhouse_app/greenhouses/'},
                    {'label': greenhouse.name, 'url': f'/greenhouse_app/greenhouses/{greenhouse.id}/'},
                    {'label': 'Disease Detection', 'url': f'/greenhouse_app/greenhouses/{greenhouse.id}/diagnosis/'},
                    {'label': 'New Diagnosis', 'url': None},
                ],
            })

        if len(images) > 5:
            messages.error(request, 'Maximum 5 images per diagnosis.')
            return redirect('diagnosis:diagnosis_new', greenhouse_id=greenhouse.id)

        # Validate file types
        allowed_types = {'image/jpeg', 'image/png', 'image/webp', 'image/jpg'}
        for img in images:
            if img.content_type not in allowed_types:
                messages.error(request, f'Unsupported file type: {img.content_type}. Use JPEG or PNG.')
                return redirect('diagnosis:diagnosis_new', greenhouse_id=greenhouse.id)

        bed_id = request.POST.get('bed_id') or None
        crop_id = request.POST.get('crop_id') or None
        plant_part = request.POST.get('plant_part', 'leaf')
        notes = request.POST.get('notes', '')

        bed = get_object_or_404(Bed, id=bed_id, house__greenhouse=greenhouse) if bed_id else None
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

        # Save images
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
                f = diag_image.image.open('rb')
                image_files.append(('images', (diag_image.image.name, f, 'image/jpeg')))
            except Exception as e:
                logger.error(f'Cannot open saved image: {e}')

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
            diag_request.status = DiagnosisRequest.Status.FAILED
            diag_request.ml_error = str(e)
            diag_request.save()
            messages.error(request, f'An error occurred: {e}')
            return redirect('diagnosis:diagnosis_list', greenhouse_id=greenhouse.id)

        finally:
            for _, (_, f, _) in image_files:
                try:
                    f.close()
                except Exception:
                    pass

        elapsed_ms = int(time.time() * 1000) - start_ms

        # Save results
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
        'breadcrumbs': [
            {'label': 'Greenhouses', 'url': '/greenhouse_app/greenhouses/'},
            {'label': greenhouse.name, 'url': f'/greenhouse_app/greenhouses/{greenhouse.id}/'},
            {'label': 'Disease Detection', 'url': f'/greenhouse_app/greenhouses/{greenhouse.id}/diagnosis/'},
            {'label': 'New Diagnosis', 'url': None},
        ],
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

    # Handle farmer feedback POST
    if request.method == 'POST':
        result_id = request.POST.get('result_id')
        feedback = request.POST.get('farmer_feedback')
        farmer_notes = request.POST.get('farmer_notes', '')

        if result_id and feedback:
            result = get_object_or_404(DiagnosisResult, id=result_id, request=diag_request)
            result.farmer_feedback = feedback
            result.farmer_notes = farmer_notes
            result.save()
            messages.success(request, 'Feedback saved.')

        return redirect('diagnosis:diagnosis_detail', greenhouse_id=greenhouse.id, pk=pk)

    return render(request, 'diagnosis/diagnosis_detail.html', {
        'greenhouse': greenhouse,
        'diag_request': diag_request,
        'results': diag_request.results.order_by('-confidence'),
        'images': diag_request.images.all(),
        'breadcrumbs': [
            {'label': 'Greenhouses', 'url': '/greenhouse_app/greenhouses/'},
            {'label': greenhouse.name, 'url': f'/greenhouse_app/greenhouses/{greenhouse.id}/'},
            {'label': 'Disease Detection', 'url': f'/greenhouse_app/greenhouses/{greenhouse.id}/diagnosis/'},
            {'label': f'Diagnosis #{diag_request.id}', 'url': None},
        ],
    })
