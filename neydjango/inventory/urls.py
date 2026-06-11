"""
inventory/urls.py
"""

from django.urls import path
from . import views
from . import views_template

app_name = 'inventory'

urlpatterns = [

    # ── HTML pages ────────────────────────────────────────────────────
    path(
        'greenhouse_app/greenhouses/<int:greenhouse_id>/inventory/',
        views_template.inventory_list,
        name='inventory_list',
    ),
    path(
        'greenhouse_app/greenhouses/<int:greenhouse_id>/inventory/new/',
        views_template.inventory_item_create,
        name='inventory_item_create',
    ),
    path(
        'greenhouse_app/greenhouses/<int:greenhouse_id>/inventory/<int:item_id>/',
        views_template.inventory_item_detail,
        name='inventory_item_detail',
    ),
    path(
        'greenhouse_app/greenhouses/<int:greenhouse_id>/inventory/<int:item_id>/edit/',
        views_template.inventory_item_edit,
        name='inventory_item_edit',
    ),
    path(
        'greenhouse_app/greenhouses/<int:greenhouse_id>/inventory/<int:item_id>/transactions/new/',
        views_template.transaction_create,
        name='transaction_create',
    ),
    path(
        'greenhouse_app/greenhouses/<int:greenhouse_id>/inventory/<int:item_id>/transactions/<int:transaction_id>/delete/',
        views_template.transaction_delete,
        name='transaction_delete',
    ),

    # ── JSON API ──────────────────────────────────────────────────────
    path(
        'api/v1/greenhouses/<int:greenhouse_pk>/inventory/',
        views.InventoryItemListCreateView.as_view(),
        name='api-inventory-list',
    ),
    path(
        'api/v1/greenhouses/<int:greenhouse_pk>/inventory/summary/',
        views.InventoryStockSummaryView.as_view(),
        name='api-inventory-summary',
    ),
    path(
        'api/v1/greenhouses/<int:greenhouse_pk>/inventory/<int:pk>/',
        views.InventoryItemDetailView.as_view(),
        name='api-inventory-detail',
    ),
    path(
        'api/v1/greenhouses/<int:greenhouse_pk>/inventory/<int:item_pk>/transactions/',
        views.InventoryTransactionListCreateView.as_view(),
        name='api-transaction-list',
    ),
]
