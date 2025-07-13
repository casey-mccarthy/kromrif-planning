from django.apps import AppConfig


class DkpConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'kromrif_planning.dkp'
    verbose_name = 'DKP System'
    
    def ready(self):
        import kromrif_planning.dkp.signals
