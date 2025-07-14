from django.apps import AppConfig


class RaidersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'kromrif_planning.raiders'
    verbose_name = 'Raiders'
    
    def ready(self):
        """Import signals when the app is ready"""
        import kromrif_planning.raiders.signals
        import kromrif_planning.raiders.discord_signals
        import kromrif_planning.raiders.recruitment_signals