"""
operations/views.py — DRF JSON API views
"""

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser


from accounts.models import GreenhouseMembership
from accounts.permissions import IsGreenhouseMember, IsGreenhouseOwnerOrManager, CanWriteOperations
from greenhouse_app.models import Bed, Greenhouse
from django.http import JsonResponse


from .models import Operation, OperationPhoto
from .serializers import (
    OperationListSerializer,
    OperationDetailSerializer,
    OperationWriteSerializer,
    OperationPhotoSerializer,
)


def get_greenhouse_from_bed(bed_id):
    try:
        return Bed.objects.select_related('house__greenhouse').get(pk=bed_id).house.greenhouse
    except Bed.DoesNotExist:
        return None


class OperationListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/v1/greenhouses/{gid}/operations/
         Supports filters: ?bed_id=&type=&from=&to=&crop_id=

    POST /api/v1/greenhouses/{gid}/operations/
         Log a new operation.
    """
    permission_classes = [permissions.IsAuthenticated, IsGreenhouseMember, CanWriteOperations]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return OperationWriteSerializer
        return OperationListSerializer

    def get_queryset(self):
        greenhouse_id = self.kwargs['greenhouse_pk']
        qs = Operation.objects.filter(
            bed__house__greenhouse_id=greenhouse_id
        ).select_related('performed_by', 'bed')

        # Filters
        bed_id   = self.request.query_params.get('bed_id')
        op_type  = self.request.query_params.get('type')
        from_date = self.request.query_params.get('from')
        to_date   = self.request.query_params.get('to')
        crop_id   = self.request.query_params.get('crop_id')

        if bed_id:
            qs = qs.filter(bed_id=bed_id)
        if op_type:
            qs = qs.filter(operation_type=op_type)
        if from_date:
            qs = qs.filter(performed_at__gte=from_date)
        if to_date:
            qs = qs.filter(performed_at__lte=to_date)
        if crop_id:
            qs = qs.filter(crop_id=crop_id)

        return qs

    def perform_create(self, serializer):
        serializer.save(logged_by=self.request.user)


class OperationDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/v1/greenhouses/{gid}/operations/{pk}/
    PATCH  /api/v1/greenhouses/{gid}/operations/{pk}/
    DELETE /api/v1/greenhouses/{gid}/operations/{pk}/
    """
    permission_classes = [permissions.IsAuthenticated, IsGreenhouseMember]

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return OperationWriteSerializer
        return OperationDetailSerializer

    def get_queryset(self):
        return Operation.objects.filter(
            bed__house__greenhouse_id=self.kwargs['greenhouse_pk']
        )


class OperationPhotoUploadView(APIView):
    """
    POST /api/v1/operations/{operation_pk}/photos/
    Upload photos to an existing operation.
    Accepts multipart/form-data with one or more 'images' files.
    """
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, operation_pk):
        try:
            operation = Operation.objects.get(pk=operation_pk)
        except Operation.DoesNotExist:
            return Response({'detail': 'Operation not found.'}, status=status.HTTP_404_NOT_FOUND)

        images = request.FILES.getlist('images')
        if not images:
            return Response({'detail': 'No images provided.'}, status=status.HTTP_400_BAD_REQUEST)

        created = []
        for image in images:
            caption = request.data.get('caption', '')
            photo = OperationPhoto.objects.create(
                operation=operation,
                image=image,
                caption=caption,
            )
            created.append(OperationPhotoSerializer(photo).data)

        return Response(created, status=status.HTTP_201_CREATED)



def bed_crops_api(request, greenhouse_id, bed_id):
    """Returns active crops for a specific bed as JSON — used by the form JS."""
    from greenhouse_app.models import Crop
    crops = Crop.objects.filter(
        bed_id=bed_id,
        bed__house__greenhouse_id=greenhouse_id,
        status='growing',
    ).values('id', 'crop_type', 'variety')

    data = [
        {
            'id': c['id'],
            'label': f"{c['crop_type']}" + (f" ({c['variety']})" if c['variety'] else ''),
        }
        for c in crops
    ]
    return JsonResponse({'crops': data})