from django.db import models
from django.utils import timezone
from django.conf import settings
from empresas.models import Empresa
import uuid

class UserCompanyLink(models.Model):
    """
    Modelo para gerenciar o vínculo entre usuários e empresas
    """
    STATUS_CHOICES = (
        ('pending', 'Pendente'),
        ('accepted', 'Aceito'),
        ('rejected', 'Recusado'),
        ('inactive', 'Inativo')
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='company_links',
        verbose_name='Usuário'
    )
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name='employee_links',
        verbose_name='Empresa'
    )
    position = models.CharField(
        max_length=100,
        verbose_name='Cargo'
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name='Status'
    )
    permissions = models.JSONField(
        default=dict,
        verbose_name='Permissões'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Criado em'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Atualizado em'
    )
    expires_at = models.DateTimeField(
        verbose_name='Expira em'
    )

    class Meta:
        verbose_name = 'Vínculo Usuário-Empresa'
        verbose_name_plural = 'Vínculos Usuário-Empresa'
        unique_together = ('user', 'empresa')

    def __str__(self):
        return f'{self.user.email} - {self.empresa.nome_fantasia}'

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(hours=1)
        super().save(*args, **kwargs)

    def is_expired(self):
        return timezone.now() > self.expires_at
