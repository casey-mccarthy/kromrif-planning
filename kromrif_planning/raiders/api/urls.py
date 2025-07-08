from rest_framework.routers import DefaultRouter
from .views import CharacterViewSet, RankViewSet, CharacterOwnershipViewSet

app_name = 'raiders-api'

router = DefaultRouter()
router.register(r'characters', CharacterViewSet, basename='character')
router.register(r'ranks', RankViewSet, basename='rank')
router.register(r'ownership-history', CharacterOwnershipViewSet, basename='ownership-history')

urlpatterns = router.urls