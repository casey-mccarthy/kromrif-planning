from django.contrib import admin
from django.contrib.auth import admin as auth_admin
from django.contrib.auth.models import Group
from django.contrib import messages

from .models import User


@admin.register(User)
class UserAdmin(auth_admin.UserAdmin):
    fieldsets = auth_admin.UserAdmin.fieldsets + (
        (
            "Discord Information",
            {
                "fields": (
                    "discord_id",
                    "discord_username", 
                    "discord_discriminator",
                    "discord_avatar",
                )
            },
        ),
        (
            "Role & Guild Info",
            {
                "fields": (
                    "role_group",
                    "name",
                )
            },
        ),
    )
    
    list_display = [
        "username",
        "name", 
        "discord_username",
        "discord_discriminator",
        "role_group",
        "is_staff",
        "is_superuser",
        "is_active",
        "date_joined",
    ]
    
    list_filter = [
        "role_group",
        "is_staff",
        "is_superuser",
        "is_active",
        "date_joined",
        "groups",
    ]
    
    search_fields = [
        "username",
        "name", 
        "discord_username", 
        "discord_id",
        "email",
    ]
    
    readonly_fields = ["discord_id", "date_joined", "last_login"]
    
    ordering = ["role_group", "username"]
    
    filter_horizontal = ["groups", "user_permissions"]
    
    def get_queryset(self, request):
        """Optimize queryset with select_related and prefetch_related."""
        return super().get_queryset(request).select_related().prefetch_related('groups')
    
    def save_model(self, request, obj, form, change):
        """Override save to ensure role group synchronization."""
        super().save_model(request, obj, form, change)
        
        # The signal will handle group assignment, but we can add logging here if needed
        if change and 'role_group' in form.changed_data:
            messages.info(
                request, 
                f"User {obj.username} has been assigned to role group: {obj.get_role_display_name()}"
            )


# Custom admin actions for bulk operations with permission validation
def _validate_role_assignment_permission(request, target_role):
    """
    Validate that the current user has permission to assign the target role.
    
    Args:
        request: The Django request object
        target_role: The role being assigned
        
    Returns:
        bool: True if permission granted, False otherwise
    """
    user = request.user
    
    # Superusers can assign any role
    if user.is_superuser:
        return True
    
    # Developers can assign member, applicant, guest roles
    if user.role_group == 'developer' and target_role in ['member', 'applicant', 'guest']:
        return True
    
    # Officers can assign applicant and guest roles
    if user.role_group == 'officer' and target_role in ['applicant', 'guest']:
        return True
    
    # Recruiters can assign guest role
    if user.role_group == 'recruiter' and target_role == 'guest':
        return True
    
    return False


def assign_member_role(modeladmin, request, queryset):
    """Bulk assign member role to selected users."""
    if not _validate_role_assignment_permission(request, 'member'):
        messages.error(
            request, 
            "❌ Insufficient permissions to assign member role. "
            "Required: Developer level or higher."
        )
        return
    
    updated_count = 0
    for user in queryset:
        # Don't downgrade higher roles
        if user.role_group not in ['developer', 'officer', 'recruiter']:
            user.assign_role_group('member')
            updated_count += 1
    
    if updated_count > 0:
        messages.success(
            request, 
            f"✅ Successfully assigned member role to {updated_count} users."
        )
    else:
        messages.warning(
            request,
            "⚠️ No users were updated (users with higher roles were skipped)."
        )

assign_member_role.short_description = "Assign member role to selected users"


def assign_applicant_role(modeladmin, request, queryset):
    """Bulk assign applicant role to selected users."""
    if not _validate_role_assignment_permission(request, 'applicant'):
        messages.error(
            request,
            "❌ Insufficient permissions to assign applicant role. "
            "Required: Officer level or higher."
        )
        return
    
    updated_count = 0
    for user in queryset:
        # Don't downgrade higher roles  
        if user.role_group not in ['developer', 'officer', 'recruiter', 'member']:
            user.assign_role_group('applicant')
            updated_count += 1
    
    if updated_count > 0:
        messages.success(
            request,
            f"✅ Successfully assigned applicant role to {updated_count} users."
        )
    else:
        messages.warning(
            request,
            "⚠️ No users were updated (users with higher roles were skipped)."
        )

assign_applicant_role.short_description = "Assign applicant role to selected users"


def assign_guest_role(modeladmin, request, queryset):
    """Bulk assign guest role to selected users."""
    if not _validate_role_assignment_permission(request, 'guest'):
        messages.error(
            request,
            "❌ Insufficient permissions to assign guest role. "
            "Required: Recruiter level or higher."
        )
        return
    
    updated_count = 0
    for user in queryset:
        user.assign_role_group('guest')
        updated_count += 1
    
    messages.success(
        request,
        f"✅ Successfully assigned guest role to {updated_count} users."
    )

assign_guest_role.short_description = "Assign guest role to selected users"


# Add the custom actions to the UserAdmin
UserAdmin.actions = [
    assign_member_role,
    assign_applicant_role,
    assign_guest_role,
]