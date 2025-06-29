from django.apps import AppConfig


class AssinaturasConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'assinaturas'
    verbose_name = 'Assinaturas & Planos'

    def ready(self):
        # Importa os signals para garantir o registro quando o app é carregado
        from . import signals  # noqa: F401
