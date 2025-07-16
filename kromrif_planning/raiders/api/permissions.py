"""
Custom permissions for Discord bot API access and guild management.
"""

from rest_framework import permissions
from django.contrib.auth import get_user_model

User = get_user_model()


class IsDiscordBot(permissions.BasePermission):
    """
    Permission class for Discord bot API access.
    Allows access to users with 'bot' role or specific bot user accounts.
    """
    
    def has_permission(self, request, view):
        """
        Check if the user has Discord bot permissions.
        
        Args:
            request: The HTTP request
            view: The view being accessed
            
        Returns:
            bool: True if user has bot permissions
        """
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Allow superusers
        if request.user.is_superuser:
            return True
        
        # Allow users with 'developer' role (highest role in hierarchy)
        if hasattr(request.user, 'role_group') and request.user.role_group == 'developer':
            return True
        
        # Allow users with specific bot permissions
        if request.user.has_perm('raiders.can_use_discord_api'):
            return True
        
        # Allow users with 'officer' role for most operations
        if hasattr(request.user, 'role_group') and request.user.role_group == 'officer':
            return True
        
        return False


class IsOfficerOrHigher(permissions.BasePermission):
    """
    Permission class for officer-level operations.
    Allows access to officers, developers, and superusers.
    """
    
    def has_permission(self, request, view):
        """
        Check if the user has officer-level permissions.
        
        Args:
            request: The HTTP request
            view: The view being accessed
            
        Returns:
            bool: True if user has officer+ permissions
        """
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Allow superusers
        if request.user.is_superuser:
            return True
        
        # Check role hierarchy
        if hasattr(request.user, 'role_group'):
            officer_roles = ['developer', 'officer']
            if request.user.role_group in officer_roles:
                return True
        
        # Allow users with staff status
        if request.user.is_staff:
            return True
        
        return False


class IsRecriterOrHigher(permissions.BasePermission):
    """
    Permission class for recruiter-level operations.
    Allows access to recruiters, officers, developers, and superusers.
    """
    
    def has_permission(self, request, view):
        """
        Check if the user has recruiter-level permissions.
        
        Args:
            request: The HTTP request
            view: The view being accessed
            
        Returns:
            bool: True if user has recruiter+ permissions
        """
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Allow superusers
        if request.user.is_superuser:
            return True
        
        # Check role hierarchy
        if hasattr(request.user, 'role_group'):
            recruiter_roles = ['developer', 'officer', 'recruiter']
            if request.user.role_group in recruiter_roles:
                return True
        
        # Allow users with staff status
        if request.user.is_staff:
            return True
        
        return False


class IsMemberOrHigher(permissions.BasePermission):
    """
    Permission class for member-level operations.
    Allows access to all active guild members.
    """
    
    def has_permission(self, request, view):
        """
        Check if the user has member-level permissions.
        
        Args:
            request: The HTTP request
            view: The view being accessed
            
        Returns:
            bool: True if user has member+ permissions
        """
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Allow superusers
        if request.user.is_superuser:
            return True
        
        # Check if user is active member
        if not request.user.is_active:
            return False
        
        # Check role hierarchy (exclude guests and applicants from some operations)
        if hasattr(request.user, 'role_group'):
            member_roles = ['developer', 'officer', 'recruiter', 'member']
            if request.user.role_group in member_roles:
                return True
        
        return False


class IsOwnerOrOfficer(permissions.BasePermission):
    """
    Permission class for operations that require ownership or officer status.
    Used for character management and personal data access.
    """
    
    def has_permission(self, request, view):
        """
        Check basic authentication.
        Object-level permissions are checked in has_object_permission.
        
        Args:
            request: The HTTP request
            view: The view being accessed
            
        Returns:
            bool: True if user is authenticated
        """
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        """
        Check if the user can access this specific object.
        
        Args:
            request: The HTTP request
            view: The view being accessed
            obj: The object being accessed
            
        Returns:
            bool: True if user can access the object
        """
        # Allow superusers
        if request.user.is_superuser:
            return True
        
        # Allow officers and developers
        if hasattr(request.user, 'role_group'):
            if request.user.role_group in ['developer', 'officer']:
                return True
        
        # Allow staff users
        if request.user.is_staff:
            return True
        
        # Check object ownership
        if hasattr(obj, 'user'):
            return obj.user == request.user
        elif hasattr(obj, 'owner'):
            return obj.owner == request.user
        elif isinstance(obj, User):
            return obj == request.user
        
        return False


class ReadOnlyOrOfficer(permissions.BasePermission):
    """
    Permission class that allows read access to all members,
    but write access only to officers and higher.
    """
    
    def has_permission(self, request, view):
        """
        Check permissions based on request method.
        
        Args:
            request: The HTTP request
            view: The view being accessed
            
        Returns:
            bool: True if user has required permissions
        """
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Read permissions for all authenticated users
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions for officers and higher
        if request.user.is_superuser or request.user.is_staff:
            return True
        
        if hasattr(request.user, 'role_group'):
            if request.user.role_group in ['developer', 'officer']:
                return True
        
        return False


# Permission combinations for common use cases
class DiscordBotPermissions:
    """
    Common permission combinations for Discord bot operations.
    """
    
    # Read-only access for roster queries
    ROSTER_READ = [permissions.IsAuthenticated, IsMemberOrHigher]
    
    # Member management operations
    MEMBER_MANAGEMENT = [IsDiscordBot, IsOfficerOrHigher]
    
    # Bot-specific operations
    BOT_OPERATIONS = [IsDiscordBot]
    
    # Administrative operations
    ADMIN_OPERATIONS = [permissions.IsAdminUser]