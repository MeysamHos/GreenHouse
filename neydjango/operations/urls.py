"""
operations/urls.py

HTML pages live under /greenhouse_app/greenhouses/{id}/operations/
API endpoints live under /api/v1/greenhouses/{id}/operations/
"""

from django.urls import path
from . import views
from . import views_template

app_name = 'operations'

urlpatterns = [

    # ── HTML pages ────────────────────────────────────────────────────
    path(
        'greenhouse_app/greenhouses/<int:greenhouse_id>/operations/',
        views_template.operation_list,
        name='operation_list',
    ),
    path(
        'greenhouse_app/greenhouses/<int:greenhouse_id>/operations/new/',
        views_template.operation_create,
        name='operation_create',
    ),
    path(
        'greenhouse_app/greenhouses/<int:greenhouse_id>/operations/<int:operation_id>/',
        views_template.operation_detail,
        name='operation_detail',
    ),
    path(
        'greenhouse_app/greenhouses/<int:greenhouse_id>/operations/<int:operation_id>/edit/',
        views_template.operation_edit,
        name='operation_edit',
    ),
    path(
        'greenhouse_app/greenhouses/<int:greenhouse_id>/operations/<int:operation_id>/delete/',
        views_template.operation_delete,
        name='operation_delete',
    ),

    # ── JSON API ──────────────────────────────────────────────────────
    path(
        'api/v1/greenhouses/<int:greenhouse_pk>/operations/',
        views.OperationListCreateView.as_view(),
        name='api-operation-list',
    ),
    path(
        'api/v1/greenhouses/<int:greenhouse_pk>/operations/<int:pk>/',
        views.OperationDetailView.as_view(),
        name='api-operation-detail',
    ),
    path(
        'api/v1/operations/<int:operation_pk>/photos/',
        views.OperationPhotoUploadView.as_view(),
        name='api-operation-photos',
    ),
    path(
    'greenhouse_app/greenhouses/<int:greenhouse_id>/beds/<int:bed_id>/crops-json/',
    views_template.bed_crops_api,
    name='bed_crops_api',
    ),
    path(
    'greenhouse_app/greenhouses/<int:greenhouse_id>/inventory-items-json/',
    views_template.inventory_items_by_type_api,
    name='inventory_items_by_type_api',
    ),
]
