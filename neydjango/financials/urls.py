"""
financials/urls.py

Two sets of URL patterns:
  1. Template URLs  — /financials/<greenhouse_id>/...  (HTML pages)
  2. API URLs       — /api/v1/financials/...  and /api/v1/reports/pnl/

Wire both into the root urls.py:

    from django.urls import include, path
    urlpatterns = [
        ...
        path('financials/', include('financials.urls')),
        path('api/v1/',     include('financials.api_urls')),
    ]
"""

from django.urls import path
from . import views_template as tmpl
from . import views as api

app_name = 'financials'

# ── Template URL patterns ──────────────────────────────────────────────────────
urlpatterns = [
    # Dashboard / P&L
    path('<int:greenhouse_id>/', tmpl.financials_dashboard, name='dashboard'),

    # Sales
    path('<int:greenhouse_id>/sales/', tmpl.sale_list, name='sale_list'),
    path('<int:greenhouse_id>/sales/new/', tmpl.sale_create, name='sale_create'),
    path('<int:greenhouse_id>/sales/<int:sale_id>/edit/', tmpl.sale_edit, name='sale_edit'),
    path('<int:greenhouse_id>/sales/<int:sale_id>/delete/', tmpl.sale_delete, name='sale_delete'),

    # Expenses
    path('<int:greenhouse_id>/expenses/', tmpl.expense_list, name='expense_list'),
    path('<int:greenhouse_id>/expenses/new/', tmpl.expense_create, name='expense_create'),
    path('<int:greenhouse_id>/expenses/<int:expense_id>/edit/', tmpl.expense_edit, name='expense_edit'),
    path('<int:greenhouse_id>/expenses/<int:expense_id>/delete/', tmpl.expense_delete, name='expense_delete'),
]
