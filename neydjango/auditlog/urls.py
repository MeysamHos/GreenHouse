"""
auditlog/urls.py

Wire into root urls.py with:
    path('', include('auditlog.urls')),
"""

from django.urls import path
from . import views

app_name = 'auditlog'

urlpatterns = [
    path(
        'greenhouse_app/greenhouses/<int:greenhouse_id>/audit/',
        views.audit_log_list,
        name='audit_log_list',
    ),
    path(
        'greenhouse_app/greenhouses/<int:greenhouse_id>/audit/<int:log_id>/',
        views.audit_log_detail,
        name='audit_log_detail',
    ),
]
