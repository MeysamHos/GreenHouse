"""
financials/api_urls.py

REST API endpoints.
Include in root urls.py under 'api/v1/':

    path('api/v1/', include('financials.api_urls')),
"""

from django.urls import path
from . import views as api

urlpatterns = [
    # Sales API
    path('financials/sales/', api.SaleListCreateView.as_view(), name='api_sale_list'),
    path('financials/sales/<int:pk>/', api.SaleDetailView.as_view(), name='api_sale_detail'),

    # Expenses API
    path('financials/expenses/', api.ExpenseListCreateView.as_view(), name='api_expense_list'),
    path('financials/expenses/<int:pk>/', api.ExpenseDetailView.as_view(), name='api_expense_detail'),

    # P&L Report — the document endpoint: GET /api/v1/reports/pnl/
    path('reports/pnl/', api.pnl_report, name='api_pnl_report'),
]
