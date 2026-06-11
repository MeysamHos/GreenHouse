from rest_framework import serializers
from .models import Greenhouse, House, Bed, Crop
from accounts.serializers import MembershipSerializer


class CropSerializer(serializers.ModelSerializer):
    class Meta:
        model = Crop
        fields = ('id', 'bed', 'crop_type', 'variety', 'status',
                  'planted_at', 'expected_harvest_at', 'actual_harvest_at',
                  'plant_count', 'notes', 'created_at', 'updated_at')
        read_only_fields = ('id', 'created_at', 'updated_at')

    def validate(self, attrs):
        # If marking as harvested, actual_harvest_at should be provided
        if attrs.get('status') == Crop.Status.HARVESTED:
            if not attrs.get('actual_harvest_at'):
                raise serializers.ValidationError(
                    {"actual_harvest_at": "Provide the actual harvest date when marking a crop as harvested."}
                )
        return attrs


class BedSerializer(serializers.ModelSerializer):
    # Nested crops — read-only summary when viewing a bed
    crops = CropSerializer(many=True, read_only=True)
    active_crop = serializers.SerializerMethodField()

    class Meta:
        model = Bed
        fields = ('id', 'house', 'code', 'area_m2', 'capacity',
                  'notes', 'active_crop', 'crops', 'created_at')
        read_only_fields = ('id', 'created_at')

    def get_active_crop(self, obj):
        """Returns the single GROWING crop if one exists, else None."""
        crop = obj.crops.filter(status=Crop.Status.GROWING).first()
        if crop:
            return CropSerializer(crop).data
        return None


class HouseSerializer(serializers.ModelSerializer):
    # Nested beds summary
    beds = BedSerializer(many=True, read_only=True)
    bed_count = serializers.IntegerField(source='beds.count', read_only=True)

    class Meta:
        model = House
        fields = ('id', 'greenhouse', 'name', 'area_m2',
                  'notes', 'bed_count', 'beds', 'created_at')
        read_only_fields = ('id', 'created_at')


class GreenhouseListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing greenhouses.
    Doesn't nest the full house/bed tree — that's expensive for a list view.
    """
    owner_name = serializers.CharField(source='owner.get_full_name', read_only=True)
    house_count = serializers.IntegerField(source='houses.count', read_only=True)
    member_count = serializers.IntegerField(source='memberships.count', read_only=True)

    class Meta:
        model = Greenhouse
        fields = ('id', 'name', 'description', 'timezone', 'is_active',
                  'owner_name', 'house_count', 'member_count', 'created_at')
        read_only_fields = ('id', 'created_at')


class GreenhouseDetailSerializer(serializers.ModelSerializer):
    """
    Full serializer for retrieving a single greenhouse with its complete structure.
    Used on the greenhouse detail/dashboard page.
    """
    houses = HouseSerializer(many=True, read_only=True)
    memberships = MembershipSerializer(many=True, read_only=True)
    owner_name = serializers.CharField(source='owner.get_full_name', read_only=True)

    class Meta:
        model = Greenhouse
        fields = ('id', 'name', 'description', 'location_geojson', 'timezone',
                  'is_active', 'owner_name', 'houses', 'memberships',
                  'created_at', 'updated_at')
        read_only_fields = ('id', 'created_at', 'updated_at')


class GreenhouseWriteSerializer(serializers.ModelSerializer):
    """
    Separate write serializer for create/update.
    Keeps owner as read-only (set automatically from request.user).
    """
    class Meta:
        model = Greenhouse
        fields = ('name', 'description', 'location_geojson', 'timezone')
