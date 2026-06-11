"""
inventory/views.py — DRF JSON API views
"""

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsGreenhouseMember, IsGreenhouseOwnerOrManager, CanWriteOperations
from greenhouse_app.models import Greenhouse

from .models import InventoryItem, InventoryTransaction
from .serializers import (
    InventoryItemListSerializer,
    InventoryItemDetailSerializer,
    InventoryTransactionSerializer,
)


class InventoryItemListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/v1/greenhouses/{gid}/inventory/
         Supports filters: ?category=&low_stock=true
    POST /api/v1/greenhouses/{gid}/inventory/
    """
    permission_classes = [permissions.IsAuthenticated, IsGreenhouseMember]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return [permissions.IsAuthenticated(), IsGreenhouseOwnerOrManager()]
        return [permissions.IsAuthenticated(), IsGreenhouseMember()]

    def get_queryset(self):
        qs = InventoryItem.objects.filter(
            greenhouse_id=self.kwargs['greenhouse_pk'],
            is_active=True,
        )
        category  = self.request.query_params.get('category')
        low_stock = self.request.query_params.get('low_stock')
        if category:
            qs = qs.filter(category=category)
        if low_stock == 'true':
            qs = [item for item in qs if item.is_low_stock]
        return qs

    def perform_create(self, serializer):
        greenhouse = Greenhouse.objects.get(pk=self.kwargs['greenhouse_pk'])
        serializer.save(
            greenhouse=greenhouse,
            created_by=self.request.user,
        )


class InventoryItemDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/v1/greenhouses/{gid}/inventory/{pk}/
    PATCH  /api/v1/greenhouses/{gid}/inventory/{pk}/
    DELETE /api/v1/greenhouses/{gid}/inventory/{pk}/  (soft delete)
    """
    permission_classes = [permissions.IsAuthenticated, IsGreenhouseMember]
    serializer_class = InventoryItemDetailSerializer

    def get_queryset(self):
        return InventoryItem.objects.filter(
            greenhouse_id=self.kwargs['greenhouse_pk'],
        )

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save()


class InventoryTransactionListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/v1/greenhouses/{gid}/inventory/{item_pk}/transactions/
    POST /api/v1/greenhouses/{gid}/inventory/{item_pk}/transactions/
    """
    permission_classes = [permissions.IsAuthenticated, IsGreenhouseMember, CanWriteOperations]
    serializer_class = InventoryTransactionSerializer

    def get_queryset(self):
        return InventoryTransaction.objects.filter(
            item_id=self.kwargs['item_pk'],
            item__greenhouse_id=self.kwargs['greenhouse_pk'],
        )

    def perform_create(self, serializer):
        item = InventoryItem.objects.get(
            pk=self.kwargs['item_pk'],
            greenhouse_id=self.kwargs['greenhouse_pk'],
        )
        serializer.save(item=item, recorded_by=self.request.user)


class InventoryStockSummaryView(APIView):
    """
    GET /api/v1/greenhouses/{gid}/inventory/summary/
    Returns stock summary for all items — used by AI assistant and dashboard.
    """
    permission_classes = [permissions.IsAuthenticated, IsGreenhouseMember]

    def get(self, request, greenhouse_pk):
        items = InventoryItem.objects.filter(
            greenhouse_id=greenhouse_pk,
            is_active=True,
        )
        summary = []
        for item in items:
            stock = item.current_stock()
            summary.append({
                'id': item.id,
                'name': item.name,
                'category': item.get_category_display(),
                'unit': item.get_unit_display(),
                'current_stock': float(stock),
                'min_stock_threshold': float(item.min_stock_threshold) if item.min_stock_threshold else None,
                'is_low_stock': item.is_low_stock,
            })
        low_stock_count = sum(1 for s in summary if s['is_low_stock'])
        return Response({
            'total_items': len(summary),
            'low_stock_count': low_stock_count,
            'items': summary,
        })
