from django.db import models
from django.utils.translation import gettext_lazy as _

class ModuloPermissao(models.Model):
    """
    Modelo para definir os módulos disponíveis no sistema e suas permissões
    """
    MODULOS_CHOICES = (
        ('marketing', 'Marketing'),
        ('financeiro', 'Financeiro'),
        ('influencer', 'Influencer'),
    )

    codigo = models.CharField(
        max_length=50,
        choices=MODULOS_CHOICES,
        unique=True,
        verbose_name=_('Código do Módulo')
    )
    nome = models.CharField(
        max_length=100,
        verbose_name=_('Nome do Módulo')
    )
    descricao = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Descrição')
    )
    ativo = models.BooleanField(
        default=True,
        verbose_name=_('Ativo')
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Criado em')
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Atualizado em')
    )

    class Meta:
        verbose_name = _('Módulo')
        verbose_name_plural = _('Módulos')
        ordering = ['codigo']

    def __str__(self):
        return self.nome

    @classmethod
    def get_modulos_ativos(cls):
        """Retorna todos os módulos ativos"""
        return cls.objects.filter(ativo=True)

    @classmethod
    def get_modulo_by_codigo(cls, codigo):
        """Retorna um módulo específico pelo código"""
        try:
            return cls.objects.get(codigo=codigo, ativo=True)
        except cls.DoesNotExist:
            return None
