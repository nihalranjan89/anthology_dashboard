from django.apps import AppConfig

class AnthologyConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'anthology'

    def ready(self):
        import anthology.signals  # noqa
