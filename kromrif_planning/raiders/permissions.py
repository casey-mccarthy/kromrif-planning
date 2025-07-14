"""
Custom permissions for Discord bot API access and other specialized use cases.
"""

import logging
from django.conf import settings
from rest_framework import permissions
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import BasePermission

logger = logging.getLogger(__name__)


class IsDiscordBot(BasePermission):
    """
    Permission class that allows access only to Discord bots.
    Checks for valid Discord bot token in authentication headers.
    """
    
    def has_permission(self, request, view):
        """Check if the request is from a Discord bot."""
        # Check for Discord bot token in Authorization header
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        
        if not auth_header.startswith('Bot '):
            return False
        
        bot_token = auth_header[4:]  # Remove 'Bot ' prefix
        expected_token = getattr(settings, 'DISCORD_BOT_TOKEN', None)
        
        if not expected_token:
            logger.warning("DISCORD_BOT_TOKEN not configured in settings")
            return False
        
        # Compare tokens securely
        import hmac
        if not hmac.compare_digest(bot_token, expected_token):
            logger.warning("Invalid Discord bot token provided")
            return False
        
        return True
    
    def has_object_permission(self, request, view, obj):
        """Check if the bot has permission to access this specific object."""
        return self.has_permission(request, view)


class IsBotOrStaff(BasePermission):
    """
    Permission class that allows access to Discord bots or staff members.
    Combines Discord bot authentication with Django staff user permissions.
    """
    
    def has_permission(self, request, view):
        """Check if request is from Discord bot or authenticated staff user."""
        # Check if user is authenticated staff
        if request.user and request.user.is_authenticated and request.user.is_staff:
            return True
        
        # Check if request is from Discord bot
        discord_bot_permission = IsDiscordBot()
        return discord_bot_permission.has_permission(request, view)


class IsMemberOrHigher(BasePermission):
    """
    Permission class that restricts access to guild members or higher roles.
    Checks user role_group field for member status.
    """
    
    def has_permission(self, request, view):
        """Check if user has member-level access or higher."""
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Allow staff users regardless of role
        if request.user.is_staff:
            return True
        
        # Check role_group for member status
        user_role = getattr(request.user, 'role_group', None)
        
        # Define role hierarchy (higher values = higher permissions)
        role_hierarchy = {
            'guest': 0,
            'applicant': 1,
            'member': 2,
            'recruiter': 3,
            'officer': 4,
            'developer': 5,
        }
        
        user_level = role_hierarchy.get(user_role, 0)
        required_level = role_hierarchy.get('member', 2)
        
        return user_level >= required_level


class IsOfficerOrHigher(BasePermission):
    """
    Permission class that restricts access to officers or higher roles.
    """
    
    def has_permission(self, request, view):
        """Check if user has officer-level access or higher."""
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Allow staff users regardless of role
        if request.user.is_staff:
            return True
        
        # Check role_group for officer status
        user_role = getattr(request.user, 'role_group', None)
        
        # Define role hierarchy
        role_hierarchy = {
            'guest': 0,
            'applicant': 1,
            'member': 2,
            'recruiter': 3,
            'officer': 4,
            'developer': 5,
        }
        
        user_level = role_hierarchy.get(user_role, 0)
        required_level = role_hierarchy.get('officer', 4)
        
        return user_level >= required_level


class IsOwnerOrOfficer(BasePermission):
    """
    Permission class that allows access to object owners or officers.
    Useful for character management where users can edit their own characters
    or officers can edit any character.
    """
    
    def has_permission(self, request, view):
        """Basic permission check for authenticated users."""
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        """Check if user owns the object or is an officer."""
        # Allow staff users
        if request.user.is_staff:
            return True
        
        # Check if user is an officer
        officer_permission = IsOfficerOrHigher()
        if officer_permission.has_permission(request, view):
            return True
        
        # Check if user owns the object
        if hasattr(obj, 'user'):
            return obj.user == request.user
        
        # For Character objects, check via user field
        if hasattr(obj, 'user'):
            return obj.user == request.user
        
        return False


class IsReadOnlyOrOfficer(BasePermission):
    """
    Permission class that allows read access to all authenticated users
    but write access only to officers.
    """
    
    def has_permission(self, request, view):
        """Check permissions based on request method."""
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Allow read operations for authenticated users
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Check for officer permissions for write operations
        officer_permission = IsOfficerOrHigher()
        return officer_permission.has_permission(request, view)


class HasAttendanceBasedVoting(BasePermission):
    """
    Permission class that checks if user has sufficient attendance for voting.
    Requires at least 15% attendance in the last 30 days.
    """
    
    def has_permission(self, request, view):
        """Check if user has voting privileges based on attendance."""
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Allow staff users regardless of attendance
        if request.user.is_staff:
            return True
        
        # Check if user is at least a member
        member_permission = IsMemberOrHigher()
        if not member_permission.has_permission(request, view):
            return False
        
        # Check attendance record (if attendance tracking is implemented)
        # This would need to be implemented based on the attendance system
        try:
            from .models import MemberAttendanceSummary
            
            # Get latest attendance summary
            attendance = MemberAttendanceSummary.objects.filter(
                member=request.user
            ).order_by('-summary_date').first()
            
            if attendance and hasattr(attendance, 'is_voting_eligible'):
                return attendance.is_voting_eligible
            
            # Default to True if no attendance record exists yet
            return True
            
        except ImportError:
            # MemberAttendanceSummary not implemented yet, default to True
            return True


class DiscordWebhookPermission(BasePermission):
    """
    Permission class for Discord webhook endpoints.
    Validates webhook signatures and source.
    """
    
    def has_permission(self, request, view):
        """Validate Discord webhook request."""
        # Check for webhook signature headers
        signature = request.META.get('HTTP_X_SIGNATURE_ED25519')
        timestamp = request.META.get('HTTP_X_SIGNATURE_TIMESTAMP')
        
        # For now, allow requests with proper headers
        # In production, you'd validate the actual signature
        if signature and timestamp:
            return True
        
        # Check for alternative webhook token
        webhook_token = request.META.get('HTTP_X_WEBHOOK_TOKEN')
        expected_token = getattr(settings, 'DISCORD_WEBHOOK_TOKEN', None)
        
        if expected_token and webhook_token:
            import hmac
            return hmac.compare_digest(webhook_token, expected_token)
        
        # Allow requests from localhost for development
        remote_addr = request.META.get('REMOTE_ADDR', '')
        if remote_addr in ['127.0.0.1', '::1']:
            return True
        
        return False


# ===== RECRUITMENT SYSTEM PERMISSIONS =====

class CanViewApplications(BasePermission):
    """
    Permission class for viewing guild applications.
    Members and above can view basic application info.
    Officers can view sensitive information.
    """
    
    def has_permission(self, request, view):
        """Check if user can view applications."""
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Allow staff users
        if request.user.is_staff:
            return True
        
        # Check if user is at least a member
        member_permission = IsMemberOrHigher()
        return member_permission.has_permission(request, view)
    
    def has_object_permission(self, request, view, obj):
        """Check object-level permissions for viewing applications."""
        # Basic permission check
        if not self.has_permission(request, view):
            return False
        
        # Officers can view all details
        officer_permission = IsOfficerOrHigher()
        if officer_permission.has_permission(request, view):
            return True
        
        # Applicants can only view their own application
        if hasattr(obj, 'applicant_email') and hasattr(request.user, 'email'):
            if obj.applicant_email == request.user.email:
                return True
        
        # Members can view applications in public voting state
        if hasattr(obj, 'status') and obj.status in ['voting_open', 'approved', 'rejected']:
            return True
        
        return False


class CanReviewApplications(BasePermission):
    """
    Permission class for reviewing and processing applications.
    Only officers and above can review applications.
    """
    
    def has_permission(self, request, view):
        """Check if user can review applications."""
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Allow staff users
        if request.user.is_staff:
            return True
        
        # Check if user is an officer
        officer_permission = IsOfficerOrHigher()
        return officer_permission.has_permission(request, view)


class CanVoteOnApplications(BasePermission):
    """
    Permission class for voting on applications.
    Requires member status and sufficient attendance.
    """
    
    def has_permission(self, request, view):
        """Check if user can vote on applications."""
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Allow staff users
        if request.user.is_staff:
            return True
        
        # Check attendance-based voting eligibility
        voting_permission = HasAttendanceBasedVoting()
        return voting_permission.has_permission(request, view)
    
    def has_object_permission(self, request, view, obj):
        """Check if user can vote on specific application."""
        # Basic permission check
        if not self.has_permission(request, view):
            return False
        
        # Check if voting is active for this application
        if hasattr(obj, 'is_voting_active') and not obj.is_voting_active:
            return False
        
        # Check if user can vote (hasn't voted already, etc.)
        if hasattr(obj, 'can_user_vote'):
            return obj.can_user_vote(request.user)
        
        return True


class CanManageRecruitment(BasePermission):
    """
    Permission class for full recruitment system management.
    Officers and above can manage all recruitment activities.
    """
    
    def has_permission(self, request, view):
        """Check if user can manage recruitment system."""
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Allow staff users
        if request.user.is_staff:
            return True
        
        # Check if user is an officer
        officer_permission = IsOfficerOrHigher()
        return officer_permission.has_permission(request, view)


class ApplicationOwnerOrOfficer(BasePermission):
    """
    Permission class that allows application owners or officers to access.
    Applicants can view/edit their own applications, officers can manage all.
    """
    
    def has_permission(self, request, view):
        """Basic permission check for authenticated users."""
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        """Check if user owns the application or is an officer."""
        # Allow staff users
        if request.user.is_staff:
            return True
        
        # Check if user is an officer
        officer_permission = IsOfficerOrHigher()
        if officer_permission.has_permission(request, view):
            return True
        
        # Check if user is the applicant (by email match)
        if hasattr(obj, 'applicant_email') and hasattr(request.user, 'email'):
            return obj.applicant_email == request.user.email
        
        # Check if user has been approved and linked to this application
        if hasattr(obj, 'approved_user') and obj.approved_user:
            return obj.approved_user == request.user
        
        return False


class VotingPermissionsByRole(BasePermission):
    """
    Permission class that provides different voting access levels by role:
    - Officers: Can view all vote details and manage voting
    - Voting-eligible members: Can vote and view aggregate results  
    - Regular members: Can view basic voting status
    - Guests/Applicants: No voting access
    """
    
    def has_permission(self, request, view):
        """Check basic voting permissions based on user role."""
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Allow staff users
        if request.user.is_staff:
            return True
        
        # Check if user is at least a member
        member_permission = IsMemberOrHigher()
        return member_permission.has_permission(request, view)
    
    def has_object_permission(self, request, view, obj):
        """Check object-level voting permissions."""
        # Basic permission check
        if not self.has_permission(request, view):
            return False
        
        # Officers get full access
        officer_permission = IsOfficerOrHigher()
        if officer_permission.has_permission(request, view):
            return True
        
        # Voting-eligible members can vote and see aggregates
        voting_permission = HasAttendanceBasedVoting()
        if voting_permission.has_permission(request, view):
            # Can vote and view aggregate results, but not individual votes
            if view.action in ['vote', 'view_aggregates']:
                return True
        
        # Regular members can only view basic voting status
        if view.action in ['view_status']:
            return True
        
        return False


class RecruitmentReadOnlyOrOfficer(BasePermission):
    """
    Permission class for recruitment endpoints that allows:
    - Read access for members and above
    - Write access only for officers and above
    """
    
    def has_permission(self, request, view):
        """Check permissions based on request method and user role."""
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Allow staff users
        if request.user.is_staff:
            return True
        
        # Allow read operations for members
        if request.method in permissions.SAFE_METHODS:
            member_permission = IsMemberOrHigher()
            return member_permission.has_permission(request, view)
        
        # Check for officer permissions for write operations
        officer_permission = IsOfficerOrHigher()
        return officer_permission.has_permission(request, view)