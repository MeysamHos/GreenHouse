from rest_framework.permissions import BasePermission
from .models import GreenhouseMembership


def get_membership(user, greenhouse_id):
    """
    Helper: returns the GreenhouseMembership for this user+greenhouse,
    or None if the user has no membership.
    Used by all permission classes below.
    """
    try:
        return GreenhouseMembership.objects.get(
            user=user,
            greenhouse_id=greenhouse_id
        )
    except GreenhouseMembership.DoesNotExist:
        return None


class IsGreenhouseMember(BasePermission):
    """
    Allows any authenticated user who has ANY role in the greenhouse.
    The greenhouse_id must be in the URL kwargs as 'greenhouse_pk' or 'pk'.
    """
    message = "You are not a member of this greenhouse."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        greenhouse_id = (
            view.kwargs.get('greenhouse_pk') or
            view.kwargs.get('pk')
        )
        if not greenhouse_id:
            return True  # let the view handle it
        return get_membership(request.user, greenhouse_id) is not None


class IsGreenhouseOwnerOrManager(BasePermission):
    """
    Allows only Owner and Manager roles.
    Use on endpoints that change structure (adding houses, beds, crops).
    """
    message = "Only greenhouse Owners and Managers can perform this action."

    ALLOWED_ROLES = {
        GreenhouseMembership.Role.OWNER,
        GreenhouseMembership.Role.MANAGER,
    }

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        greenhouse_id = (
            view.kwargs.get('greenhouse_pk') or
            view.kwargs.get('pk')
        )
        if not greenhouse_id:
            return True
        membership = get_membership(request.user, greenhouse_id)
        return membership is not None and membership.role in self.ALLOWED_ROLES


class IsGreenhouseOwner(BasePermission):
    """
    Allows only the Owner role.
    Use on destructive actions (delete greenhouse, manage billing).
    """
    message = "Only the greenhouse Owner can perform this action."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        greenhouse_id = (
            view.kwargs.get('greenhouse_pk') or
            view.kwargs.get('pk')
        )
        if not greenhouse_id:
            return True
        membership = get_membership(request.user, greenhouse_id)
        return (
            membership is not None and
            membership.role == GreenhouseMembership.Role.OWNER
        )


class CanWriteOperations(BasePermission):
    """
    Allows Owner, Manager, and Operator to log daily operations.
    Consultants and Guests are read-only.
    """
    message = "Consultants and guests cannot log operations."

    ALLOWED_ROLES = {
        GreenhouseMembership.Role.OWNER,
        GreenhouseMembership.Role.MANAGER,
        GreenhouseMembership.Role.OPERATOR,
    }

    def has_permission(self, request, view):
        from rest_framework.permissions import SAFE_METHODS
        if request.method in SAFE_METHODS:
            return True  # reads are always allowed for members
        if not request.user or not request.user.is_authenticated:
            return False
        greenhouse_id = (
            view.kwargs.get('greenhouse_pk') or
            view.kwargs.get('pk')
        )
        if not greenhouse_id:
            return True
        membership = get_membership(request.user, greenhouse_id)
        return membership is not None and membership.role in self.ALLOWED_ROLES

def get_role_context(greenhouse, user):
    """
    Returns (user_role, can_write_operations) for this user+greenhouse —
    for use in template views that need to show/hide UI elements based on
    role, without duplicating role-set logic that already lives in
    CanWriteOperations above.

    can_write_operations reuses CanWriteOperations.ALLOWED_ROLES directly,
    so there is exactly ONE place in the codebase that defines "which
    roles can write operations" — this function and the DRF permission
    class both read from the same source, they can never drift apart.

    Returns (None, False) if the user has no membership in this greenhouse.
    """
    membership = get_membership(user, greenhouse.id)
    user_role = membership.role if membership else None
    can_write_operations = (
        membership is not None and membership.role in CanWriteOperations.ALLOWED_ROLES
    )
    return user_role, can_write_operations
