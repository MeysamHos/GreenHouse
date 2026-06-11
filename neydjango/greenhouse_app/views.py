from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied

from accounts.models import GreenhouseMembership
from accounts.permissions import (
    IsGreenhouseMember,
    IsGreenhouseOwnerOrManager,
    IsGreenhouseOwner,
)
from .models import Greenhouse, House, Bed, Crop
from .serializers import (
    GreenhouseListSerializer,
    GreenhouseDetailSerializer,
    GreenhouseWriteSerializer,
    HouseSerializer,
    BedSerializer,
    CropSerializer,
)


# ─────────────────────────────────────────────
# Greenhouse views
# ─────────────────────────────────────────────

class GreenhouseListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/v1/greenhouses/        — list greenhouses the user belongs to
    POST /api/v1/greenhouses/        — create a new greenhouse
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return GreenhouseWriteSerializer
        return GreenhouseListSerializer

    def get_queryset(self):
        # User sees only greenhouses where they have a membership
        user = self.request.user
        greenhouse_ids = GreenhouseMembership.objects.filter(
            user=user
        ).values_list('greenhouse_id', flat=True)
        return Greenhouse.objects.filter(id__in=greenhouse_ids, is_active=True)

    def perform_create(self, serializer):
        # Save the greenhouse with the current user as owner
        greenhouse = serializer.save(owner=self.request.user)
        # Automatically create an OWNER membership for the creator
        GreenhouseMembership.objects.create(
            user=self.request.user,
            greenhouse=greenhouse,
            role=GreenhouseMembership.Role.OWNER
        )


class GreenhouseDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/v1/greenhouses/{pk}/  — full detail with houses, beds, members
    PATCH  /api/v1/greenhouses/{pk}/  — update name, description, timezone
    DELETE /api/v1/greenhouses/{pk}/  — soft-delete (owner only)
    """
    def get_permissions(self):
        if self.request.method == 'DELETE':
            return [IsGreenhouseOwner()]
        if self.request.method in ('PUT', 'PATCH'):
            return [IsGreenhouseOwnerOrManager()]
        return [IsGreenhouseMember()]

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return GreenhouseWriteSerializer
        return GreenhouseDetailSerializer

    def get_queryset(self):
        return Greenhouse.objects.filter(is_active=True)

    def perform_destroy(self, instance):
        # Soft delete — keeps data, just hides the greenhouse
        instance.is_active = False
        instance.save()


# ─────────────────────────────────────────────
# House views
# ─────────────────────────────────────────────

class HouseListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/v1/greenhouses/{greenhouse_pk}/houses/
    POST /api/v1/greenhouses/{greenhouse_pk}/houses/
    """
    serializer_class = HouseSerializer

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsGreenhouseOwnerOrManager()]
        return [IsGreenhouseMember()]

    def get_queryset(self):
        return House.objects.filter(
            greenhouse_id=self.kwargs['greenhouse_pk']
        )

    def perform_create(self, serializer):
        greenhouse = Greenhouse.objects.get(pk=self.kwargs['greenhouse_pk'])
        serializer.save(greenhouse=greenhouse)


class HouseDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/v1/greenhouses/{greenhouse_pk}/houses/{pk}/
    PATCH  /api/v1/greenhouses/{greenhouse_pk}/houses/{pk}/
    DELETE /api/v1/greenhouses/{greenhouse_pk}/houses/{pk}/
    """
    serializer_class = HouseSerializer

    def get_permissions(self):
        if self.request.method in ('PUT', 'PATCH', 'DELETE'):
            return [IsGreenhouseOwnerOrManager()]
        return [IsGreenhouseMember()]

    def get_queryset(self):
        return House.objects.filter(
            greenhouse_id=self.kwargs['greenhouse_pk']
        )


# ─────────────────────────────────────────────
# Bed views
# ─────────────────────────────────────────────

class BedListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/v1/greenhouses/{greenhouse_pk}/houses/{house_pk}/beds/
    POST /api/v1/greenhouses/{greenhouse_pk}/houses/{house_pk}/beds/
    """
    serializer_class = BedSerializer

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsGreenhouseOwnerOrManager()]
        return [IsGreenhouseMember()]

    def get_queryset(self):
        return Bed.objects.filter(
            house_id=self.kwargs['house_pk'],
            house__greenhouse_id=self.kwargs['greenhouse_pk']
        )

    def perform_create(self, serializer):
        house = House.objects.get(
            pk=self.kwargs['house_pk'],
            greenhouse_id=self.kwargs['greenhouse_pk']
        )
        serializer.save(house=house)


class BedDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/v1/greenhouses/{greenhouse_pk}/houses/{house_pk}/beds/{pk}/
    PATCH  /api/v1/greenhouses/{greenhouse_pk}/houses/{house_pk}/beds/{pk}/
    DELETE /api/v1/greenhouses/{greenhouse_pk}/houses/{house_pk}/beds/{pk}/
    """
    serializer_class = BedSerializer

    def get_permissions(self):
        if self.request.method in ('PUT', 'PATCH', 'DELETE'):
            return [IsGreenhouseOwnerOrManager()]
        return [IsGreenhouseMember()]

    def get_queryset(self):
        return Bed.objects.filter(
            house_id=self.kwargs['house_pk'],
            house__greenhouse_id=self.kwargs['greenhouse_pk']
        )


# ─────────────────────────────────────────────
# Crop views
# ─────────────────────────────────────────────

class CropListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/v1/greenhouses/{greenhouse_pk}/beds/{bed_pk}/crops/
    POST /api/v1/greenhouses/{greenhouse_pk}/beds/{bed_pk}/crops/
    """
    serializer_class = CropSerializer

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsGreenhouseOwnerOrManager()]
        return [IsGreenhouseMember()]

    def get_queryset(self):
        return Crop.objects.filter(
            bed_id=self.kwargs['bed_pk'],
            bed__house__greenhouse_id=self.kwargs['greenhouse_pk']
        )

    def perform_create(self, serializer):
        bed = Bed.objects.get(
            pk=self.kwargs['bed_pk'],
            house__greenhouse_id=self.kwargs['greenhouse_pk']
        )
        serializer.save(bed=bed)


class CropDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET   /api/v1/greenhouses/{greenhouse_pk}/beds/{bed_pk}/crops/{pk}/
    PATCH /api/v1/greenhouses/{greenhouse_pk}/beds/{bed_pk}/crops/{pk}/
    """
    serializer_class = CropSerializer

    def get_permissions(self):
        if self.request.method in ('PUT', 'PATCH', 'DELETE'):
            return [IsGreenhouseOwnerOrManager()]
        return [IsGreenhouseMember()]

    def get_queryset(self):
        return Crop.objects.filter(
            bed_id=self.kwargs['bed_pk'],
            bed__house__greenhouse_id=self.kwargs['greenhouse_pk']
        )
