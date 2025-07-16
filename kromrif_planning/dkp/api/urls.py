"""
DKP API URL configuration.
"""

from rest_framework.routers import DefaultRouter
from .views import UserPointsSummaryViewSet, PointAdjustmentViewSet, DKPManagementViewSet

app_name = 'dkp-api'

router = DefaultRouter()
router.register(r'summaries', UserPointsSummaryViewSet, basename='summary')
router.register(r'adjustments', PointAdjustmentViewSet, basename='adjustment')
router.register(r'management', DKPManagementViewSet, basename='management')

urlpatterns = router.urls