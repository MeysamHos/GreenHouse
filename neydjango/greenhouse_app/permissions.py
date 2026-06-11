from rest_framework import permissions
from accounts.models import GreenhouseMembership

class HasGreenhouseRole(permissions.BasePermission):
    """
    Base object-level permission mapping logic to evaluate authorization 
    based on custom business definitions linked to granular roles.
    """
    
    def get_user_role(self, request, view):
        # Extract greenhouse context dynamically via URL parameters
        greenhouse_id = view.kwargs.get('greenhouse_id') or request.data.get('greenhouse_id')
        if not greenhouse_id or not request.user.is_authenticated:
            return None
        
        try:
            membership = GreenhouseMembership.objects.get(
                user=request.user, 
                greenhouse_id=greenhouse_id
            )
            return membership.role
        except GreenhouseMembership.DoesNotExist:
            return None


class IsGreenhouseOwnerOrManager(HasGreenhouseRole):
    """
    Grants access only to structural controllers (Owners or Managers).
    """
    def has_permission(self, request, view):
        role = self.get_user_role(request, view)
        return role in ['owner', 'manager']


class IsGreenhouseOperator(HasGreenhouseRole):
    """
    Grants execution validation to field workers logging active metrics.
    """
    def has_permission(self, request, view):
        role = self.get_user_role(request, view)
        
        # Read-only operations allowed across members
        if request.method in permissions.SAFE_METHODS and role is not None:
            return True
            
        # Writes restricted to active operating tiers
        return role in ['owner', 'manager', 'operator']


class IsConsultantOrAbove(HasGreenhouseRole):
    """
    Allows structural viewing rights and annotation pathways for agricultural specialists.
    """
    def has_permission(self, request, view):
        role = self.get_user_role(request, view)
        if role is None:
            return False
            
        if request.method in permissions.SAFE_METHODS:
            return True
            
        # Consultants can issue analysis recommendations, not structural parameters
        return role in ['owner', 'manager', 'consultant']