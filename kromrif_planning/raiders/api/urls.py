from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import (
    CharacterViewSet, RankViewSet, CharacterOwnershipViewSet,
    EventViewSet, RaidViewSet, RaidAttendanceViewSet,
    ItemViewSet, LootDistributionViewSet, LootAuditLogViewSet,
    MemberAttendanceSummaryViewSet
)
from .discord_api import DiscordRosterViewSet, DiscordMemberManagementViewSet
from .discord_webhook import DiscordWebhookView, DiscordWebhookAPIView

app_name = 'raiders-api'

router = DefaultRouter()
router.register(r'characters', CharacterViewSet, basename='character')
router.register(r'ranks', RankViewSet, basename='rank')
router.register(r'ownership-history', CharacterOwnershipViewSet, basename='ownership-history')
router.register(r'events', EventViewSet, basename='event')
router.register(r'raids', RaidViewSet, basename='raid')
router.register(r'attendance', RaidAttendanceViewSet, basename='attendance')
router.register(r'attendance-summaries', MemberAttendanceSummaryViewSet, basename='attendance-summary')
router.register(r'items', ItemViewSet, basename='item')
router.register(r'loot-distributions', LootDistributionViewSet, basename='loot-distribution')
router.register(r'audit-logs', LootAuditLogViewSet, basename='audit-log')

# Discord API endpoints (for bot access)
router.register(r'discord/roster', DiscordRosterViewSet, basename='discord-roster')
router.register(r'discord/members', DiscordMemberManagementViewSet, basename='discord-members')

urlpatterns = router.urls + [
    path('webhooks/discord/', DiscordWebhookView.as_view(), name='discord-webhook'),
    path('webhooks/discord/api/', DiscordWebhookAPIView.as_view(), name='discord-webhook-api'),
]