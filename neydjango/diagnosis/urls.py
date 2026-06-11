"""
diagnosis/urls.py

HTML pages:  /greenhouse_app/greenhouses/<id>/diagnosis/...
API:         /api/v1/diagnose/...

Wire into root urls.py:
    path('api/v1/',         include('diagnosis.urls')),   # API routes
    path('greenhouse_app/', include('diagnosis.html_urls')), # HTML routes — see note below

Actually simpler: both are in this one file, both included from root.
HTML routes start with greenhouse_app/greenhouses/...
API routes start with diagnose/...
"""

from django.urls import path
from .views import DiagnoseView, DiagnoseListView, DiagnoseDetailView, DiagnosisFeedbackView
from . import views_template

app_name = 'diagnosis'

urlpatterns = [

    # ── HTML pages ─────────────────────────────────────────────────────
    path(
        'greenhouse_app/greenhouses/<int:greenhouse_id>/diagnosis/',
        views_template.diagnosis_list,
        name='diagnosis_list',
    ),
    path(
        'greenhouse_app/greenhouses/<int:greenhouse_id>/diagnosis/new/',
        views_template.diagnosis_new,
        name='diagnosis_new',
    ),
    path(
        'greenhouse_app/greenhouses/<int:greenhouse_id>/diagnosis/<int:pk>/',
        views_template.diagnosis_detail,
        name='diagnosis_detail',
    ),

    # ── JSON API ───────────────────────────────────────────────────────
    path('diagnose/',          DiagnoseView.as_view(),       name='diagnose'),
    path('diagnose/list/',     DiagnoseListView.as_view(),   name='diagnose-list'),
    path('diagnose/<int:pk>/', DiagnoseDetailView.as_view(), name='diagnose-detail'),
    path(
        'diagnose/<int:pk>/results/<int:result_id>/feedback/',
        DiagnosisFeedbackView.as_view(),
        name='diagnose-feedback',
    ),
]
