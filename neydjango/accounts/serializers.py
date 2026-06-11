from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import User, GreenhouseMembership
from django.contrib.auth import get_user_model

User = get_user_model()

class UserRegistrationSerializer(serializers.ModelSerializer):
    """
    Used for POST /api/v1/auth/register
    Accepts password + password_confirm, validates they match,
    hashes the password before saving (never store plain text).
    """
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password]
    )
    password_confirm = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name',
                  'password', 'password_confirm', 'phone', 'locale')

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError(
                {"password": "Passwords do not match."}
            )
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        # create_user handles password hashing
        user = User.objects.create_user(**validated_data)
        return user


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Used for GET/PATCH /api/v1/auth/me
    Returns the authenticated user's own profile.
    Password is excluded — there is a separate change-password endpoint.
    """
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name',
                  'phone', 'locale', 'avatar', 'date_joined', 'last_login')
        read_only_fields = ('id', 'username', 'date_joined', 'last_login')


class MembershipSerializer(serializers.ModelSerializer):
    """
    Used when listing who belongs to a greenhouse and with what role.
    Nested user info is read-only; only 'role' is writable via this serializer.
    """
    user = UserProfileSerializer(read_only=True)
    user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source='user',
        write_only=True
    )

    class Meta:
        model = GreenhouseMembership
        fields = ('id', 'user', 'user_id', 'role', 'joined_at', 'invited_by')
        read_only_fields = ('id', 'joined_at', 'invited_by')

class UserMinimalSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'full_name']

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username