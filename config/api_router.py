from django.conf import settings
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.routers import SimpleRouter

from kromrif_planning.users.api.views import UserViewSet

router = DefaultRouter() if settings.DEBUG else SimpleRouter()

router.register("users", UserViewSet)


app_name = "api"
urlpatterns = [
    # Include the default router URLs
    *router.urls,
    # Include raiders API URLs
    path("raiders/", include("kromrif_planning.raiders.api.urls")),
    # Include Discord bot API URLs
    path("discord/", include("kromrif_planning.raiders.api.discord_urls")),
    # Include DKP API URLs
    path("dkp/", include("kromrif_planning.dkp.api.urls")),
]
