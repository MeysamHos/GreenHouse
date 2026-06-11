"""
reports/urls.py

HTML pages:  /greenhouse_app/greenhouses/<id>/reports/...
API:         /api/v1/greenhouses/<id>/reports/...

Wire into root urls.py:
    path('', include('reports.urls')),
"""

from django.urls import path
from . import views
from . import views_template

app_name = 'reports'

urlpatterns = [

    # ── HTML pages ────────────────────────────────────────────────────
    path(
        'greenhouse_app/greenhouses/<int:greenhouse_id>/reports/',
        views_template.reports_index,
        name='index',
    ),
    path(
        'greenhouse_app/greenhouses/<int:greenhouse_id>/reports/pnl/',
        views_template.report_pnl,
        name='pnl',
    ),
    path(
        'greenhouse_app/greenhouses/<int:greenhouse_id>/reports/crops/',
        views_template.report_crops,
        name='crops',
    ),
    path(
        'greenhouse_app/greenhouses/<int:greenhouse_id>/reports/operations/',
        views_template.report_operations,
        name='operations',
    ),
    path(
        'greenhouse_app/greenhouses/<int:greenhouse_id>/reports/inventory/',
        views_template.report_inventory,
        name='inventory',
    ),

    # ── JSON API ──────────────────────────────────────────────────────
    path(
        'api/v1/greenhouses/<int:greenhouse_pk>/reports/pnl/',
        views.api_pnl,
        name='api-pnl',
    ),
    path(
        'api/v1/greenhouses/<int:greenhouse_pk>/reports/crops/',
        views.api_crop_report,
        name='api-crops',
    ),
    path(
        'api/v1/greenhouses/<int:greenhouse_pk>/reports/operations/',
        views.api_operations_report,
        name='api-operations',
    ),
    path(
        'api/v1/greenhouses/<int:greenhouse_pk>/reports/inventory/',
        views.api_inventory_report,
        name='api-inventory',
    ),
]
