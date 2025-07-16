import contextlib

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class UsersConfig(AppConfig):
    name = "kromrif_planning.users"
    verbose_name = _("Users")

    def ready(self):
        with contextlib.suppress(ImportError):
            import kromrif_planning.users.signals  # noqa: F401