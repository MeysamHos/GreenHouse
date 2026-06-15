"""
reports/api_urls.py  — DRF JSON API endpoints

Include in root urls.py as:
    path('api/v1/', include('reports.api_urls')),
"""

from django.urls import path
from . import views

urlpatterns = [
    path(
        'greenhouses/<int:greenhouse_pk>/reports/pnl/',
        views.api_pnl,
        name='api-reports-pnl',
    ),
    path(
        'greenhouses/<int:greenhouse_pk>/reports/crops/',
        views.api_crop_report,
        name='api-reports-crops',
    ),
    path(
        'greenhouses/<int:greenhouse_pk>/reports/operations/',
        views.api_operations_report,
        name='api-reports-operations',
    ),
    path(
        'greenhouses/<int:greenhouse_pk>/reports/inventory/',
        views.api_inventory_report,
        name='api-reports-inventory',
    ),
]