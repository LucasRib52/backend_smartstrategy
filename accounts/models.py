from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _

class User(AbstractUser):
    """
    Modelo base de usuário que estende o User padrão do Django
    """
    USER_TYPE_CHOICES = (
        ('PF', 'Pessoa Física'),
        ('PJ', 'Pessoa Jurídica'),
    )

    # Sobrescrevendo campos do AbstractUser para torná-los opcionais
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)

    # Campos personalizados
    email = models.EmailField(
        'Email',
        unique=True,
        help_text='Email do usuário'
    )
    user_type = models.CharField(
        'Tipo de Usuário',
        max_length=2,
        choices=USER_TYPE_CHOICES,
        help_text='Tipo de usuário (PF ou PJ)'
    )
    empresa_atual = models.ForeignKey(
        'empresas.Empresa',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='usuarios_ativos',
        verbose_name=_('Empresa Atual')
    )

    # Campos de auditoria
    created_at = models.DateTimeField(
        'Criado em',
        auto_now_add=True
    )
    updated_at = models.DateTimeField(
        'Atualizado em',
        auto_now=True
    )

    # Configurações do modelo
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'user_type']

    class Meta:
        verbose_name = _('Usuário')
        verbose_name_plural = _('Usuários')

    def __str__(self):
        if self.user_type == 'PF':
            try:
                return f'{self.person_profile.name} ({self.email})'
            except:
                return self.email
        try:
            return f'{self.company_profile.company_name} ({self.email})'
        except:
            return self.email

class PersonProfile(models.Model):
    """
    Modelo para perfil de pessoa física
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='person_profile',
        verbose_name='Usuário'
    )
    name = models.CharField(
        'Nome Completo',
        max_length=255,
        null=True,
        blank=True,
        help_text='Nome completo do usuário'
    )
    cpf = models.CharField(
        'CPF',
        max_length=14,
        validators=[
            RegexValidator(
                regex=r'^\d{3}\.\d{3}\.\d{3}-\d{2}$',
                message='CPF deve estar no formato 000.000.000-00'
            )
        ],
        unique=True,
        null=True,
        blank=True,
        help_text='CPF do usuário'
    )
    phone = models.CharField(
        'Telefone',
        max_length=15,
        validators=[
            RegexValidator(
                regex=r'^\(\d{2}\) \d{5}-\d{4}$',
                message='Telefone deve estar no formato (00) 00000-0000'
            )
        ],
        null=True,
        blank=True,
        help_text='Telefone do usuário'
    )
    position = models.CharField(
        'Cargo',
        max_length=100,
        null=True,
        blank=True,
        help_text='Cargo ou função do usuário'
    )

    # Campos de auditoria
    created_at = models.DateTimeField(
        'Criado em',
        auto_now_add=True
    )
    updated_at = models.DateTimeField(
        'Atualizado em',
        auto_now=True
    )

    class Meta:
        verbose_name = 'Perfil de Pessoa Física'
        verbose_name_plural = 'Perfis de Pessoas Físicas'

    def __str__(self):
        return f'Perfil de {self.name}'

    def save(self, *args, **kwargs):
        if self.user.user_type != 'PF':
            raise ValueError('Este perfil só pode ser associado a usuários do tipo Pessoa Física')
        super().save(*args, **kwargs)

class CompanyProfile(models.Model):
    """
    Modelo para perfil de pessoa jurídica
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='company_profile',
        verbose_name='Usuário'
    )
    company_name = models.CharField(
        'Razão Social',
        max_length=255,
        null=True,
        blank=True,
        help_text='Razão social da empresa'
    )
    trade_name = models.CharField(
        'Nome Fantasia',
        max_length=255,
        null=True,
        blank=True,
        help_text='Nome fantasia da empresa'
    )
    cnpj = models.CharField(
        'CNPJ',
        max_length=18,
        validators=[
            RegexValidator(
                regex=r'^\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}$',
                message='CNPJ deve estar no formato 00.000.000/0000-00'
            )
        ],
        unique=True,
        null=True,
        blank=True,
        help_text='CNPJ da empresa'
    )
    state_registration = models.CharField(
        'Inscrição Estadual',
        max_length=20,
        null=True,
        blank=True,
        help_text='Inscrição estadual da empresa'
    )
    municipal_registration = models.CharField(
        'Inscrição Municipal',
        max_length=20,
        null=True,
        blank=True,
        help_text='Inscrição municipal da empresa'
    )
    responsible_name = models.CharField(
        'Nome do Responsável',
        max_length=255,
        null=True,
        blank=True,
        help_text='Nome do responsável pela empresa'
    )
    phone1 = models.CharField(
        'Telefone Principal',
        max_length=15,
        validators=[
            RegexValidator(
                regex=r'^\(\d{2}\) \d{5}-\d{4}$',
                message='Telefone deve estar no formato (00) 00000-0000'
            )
        ],
        null=True,
        blank=True,
        help_text='Telefone principal da empresa'
    )
    phone2 = models.CharField(
        'Telefone Secundário',
        max_length=15,
        validators=[
            RegexValidator(
                regex=r'^\(\d{2}\) \d{5}-\d{4}$',
                message='Telefone deve estar no formato (00) 00000-0000'
            )
        ],
        null=True,
        blank=True,
        help_text='Telefone secundário da empresa'
    )
    website = models.URLField(
        'Website',
        max_length=200,
        null=True,
        blank=True,
        help_text='Website da empresa'
    )

    # Campos de auditoria
    created_at = models.DateTimeField(
        'Criado em',
        auto_now_add=True
    )
    updated_at = models.DateTimeField(
        'Atualizado em',
        auto_now=True
    )

    class Meta:
        verbose_name = 'Perfil de Empresa'
        verbose_name_plural = 'Perfis de Empresas'

    def __str__(self):
        return f'Perfil de {self.company_name}'

    def save(self, *args, **kwargs):
        if self.user.user_type != 'PJ':
            raise ValueError('Este perfil só pode ser associado a usuários do tipo Pessoa Jurídica')
        super().save(*args, **kwargs)
