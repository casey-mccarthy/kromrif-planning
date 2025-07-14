"""
URL patterns for Discord Bot API endpoints.
These are separate from the main API to allow for different authentication/permissions.
"""

from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .discord_api import DiscordRosterViewSet, DiscordMemberManagementViewSet

app_name = 'discord-api'

# Create router for Discord API endpoints
discord_router = DefaultRouter()
discord_router.register(r'roster', DiscordRosterViewSet, basename='discord-roster')
discord_router.register(r'members', DiscordMemberManagementViewSet, basename='discord-members')

urlpatterns = [
    path('', include(discord_router.urls)),
]