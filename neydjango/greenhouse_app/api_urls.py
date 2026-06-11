"""
greenhouse_app/api_urls.py

REST API endpoints for greenhouses, houses, beds and crops.
Mounted at api/v1/ in the root urls.py so all API endpoints
share a consistent /api/v1/... prefix.
"""

from django.urls import path
from . import views

urlpatterns = [
    path('greenhouses/',
         views.GreenhouseListCreateView.as_view(),  name='api-greenhouse-list'),
    path('greenhouses/<int:pk>/',
         views.GreenhouseDetailView.as_view(),       name='api-greenhouse-detail'),

    path('greenhouses/<int:greenhouse_pk>/houses/',
         views.HouseListCreateView.as_view(),        name='api-house-list'),
    path('greenhouses/<int:greenhouse_pk>/houses/<int:pk>/',
         views.HouseDetailView.as_view(),            name='api-house-detail'),

    path('greenhouses/<int:greenhouse_pk>/houses/<int:house_pk>/beds/',
         views.BedListCreateView.as_view(),          name='api-bed-list'),
    path('greenhouses/<int:greenhouse_pk>/houses/<int:house_pk>/beds/<int:pk>/',
         views.BedDetailView.as_view(),              name='api-bed-detail'),

    path('greenhouses/<int:greenhouse_pk>/beds/<int:bed_pk>/crops/',
         views.CropListCreateView.as_view(),         name='api-crop-list'),
    path('greenhouses/<int:greenhouse_pk>/beds/<int:bed_pk>/crops/<int:pk>/',
         views.CropDetailView.as_view(),             name='api-crop-detail'),
]