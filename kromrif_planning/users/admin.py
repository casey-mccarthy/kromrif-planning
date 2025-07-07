from django.contrib import admin
from django.contrib.auth import admin as auth_admin
from django.contrib.auth.models import Group

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
            self.message_user(
                request, 
                f"User {obj.username} has been assigned to role group: {obj.get_role_display_name()}"
            )


# Custom admin actions for bulk operations
def assign_member_role(modeladmin, request, queryset):
    """Bulk assign member role to selected users."""
    for user in queryset:
        user.assign_role_group('member')
    modeladmin.message_user(request, f"Successfully assigned member role to {queryset.count()} users.")

assign_member_role.short_description = "Assign member role to selected users"


def assign_applicant_role(modeladmin, request, queryset):
    """Bulk assign applicant role to selected users."""
    for user in queryset:
        user.assign_role_group('applicant')
    modeladmin.message_user(request, f"Successfully assigned applicant role to {queryset.count()} users.")

assign_applicant_role.short_description = "Assign applicant role to selected users"


def assign_guest_role(modeladmin, request, queryset):
    """Bulk assign guest role to selected users."""
    for user in queryset:
        user.assign_role_group('guest')
    modeladmin.message_user(request, f"Successfully assigned guest role to {queryset.count()} users.")

assign_guest_role.short_description = "Assign guest role to selected users"


# Add the custom actions to the UserAdmin
UserAdmin.actions = [
    assign_member_role,
    assign_applicant_role,
    assign_guest_role,
]