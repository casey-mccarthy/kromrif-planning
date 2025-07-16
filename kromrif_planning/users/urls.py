"""URLs for the users app."""
from django.urls import path

from . import views

app_name = "users"
urlpatterns = [
    path("~redirect/", view=views.user_redirect_view, name="redirect"),
    path("<int:pk>/", view=views.user_detail_view, name="detail"),
]