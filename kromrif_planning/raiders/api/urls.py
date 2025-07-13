from rest_framework.routers import DefaultRouter
from .views import (
    CharacterViewSet, RankViewSet, CharacterOwnershipViewSet,
    EventViewSet, RaidViewSet, RaidAttendanceViewSet
)

app_name = 'raiders-api'

router = DefaultRouter()
router.register(r'characters', CharacterViewSet, basename='character')
router.register(r'ranks', RankViewSet, basename='rank')
router.register(r'ownership-history', CharacterOwnershipViewSet, basename='ownership-history')
router.register(r'events', EventViewSet, basename='event')
router.register(r'raids', RaidViewSet, basename='raid')
router.register(r'attendance', RaidAttendanceViewSet, basename='attendance')

urlpatterns = router.urls