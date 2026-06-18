"""
URL configuration for greenhouse project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('api/v1/auth/',    include('accounts.urls')),
    path('api/v1/',         include('greenhouse_app.api_urls')),  # ← add this
    path('api/v1/',         include('financials.api_urls')),
    path('api/v1/',         include('reports.api_urls')),             # reports has both
    path('api/v1/',         include('diagnosis.urls')),
    path('',                include('operations.urls')),
    path('',                include('inventory.urls')),
    path('',                include('reports.urls')),
    path('polls/',          include('polls.urls')),
    path('',                include('auditlog.urls')),
    path('greenhouse_app/', include('greenhouse_app.urls')),
    path('financials/',     include('financials.urls')),
    path('admin/',          admin.site.urls),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
