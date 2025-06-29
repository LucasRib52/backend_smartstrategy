from django.db import models
from django.conf import settings

class PerfilUsuario(models.Model):
    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    foto = models.ImageField(upload_to='perfil_fotos/', null=True, blank=True)
    data_atualizacao = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Perfil de {self.usuario.username}"
