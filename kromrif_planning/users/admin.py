from django.contrib import admin
from django.contrib.auth import admin as auth_admin

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
        ("Additional Info", {"fields": ("name",)}),
    )
    list_display = [
        "username",
        "name", 
        "discord_username",
        "discord_discriminator",
        "is_staff",
        "is_superuser",
    ]
    search_fields = ["name", "discord_username", "discord_id", "username"]
    readonly_fields = ["discord_id"]