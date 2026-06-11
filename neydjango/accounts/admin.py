from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, GreenhouseMembership


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    # Extend the default UserAdmin to show our extra fields
    list_display = ('username', 'email', 'first_name', 'last_name',
                    'phone', 'locale', 'is_active', 'date_joined')
    list_filter = ('locale', 'is_active', 'is_staff')
    search_fields = ('username', 'email', 'phone', 'first_name', 'last_name')

    # Add our custom fields to the edit form sections
    fieldsets = UserAdmin.fieldsets + (
        ('Platform Profile', {
            'fields': ('phone', 'locale', 'avatar')
        }),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Platform Profile', {
            'fields': ('phone', 'locale')
        }),
    )


@admin.register(GreenhouseMembership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ('user', 'greenhouse', 'role', 'joined_at', 'invited_by')
    list_filter = ('role',)
    search_fields = ('user__username', 'greenhouse__name')
    raw_id_fields = ('user', 'greenhouse', 'invited_by')
