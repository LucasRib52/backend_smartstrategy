from django.db import models
from django.contrib.auth import get_user_model
from empresas.models import Empresa
from usuariospainel.models import UserCompanyLink
from django.utils import timezone

User = get_user_model()

class ConviteUsuario(models.Model):
    """
    Modelo para gerenciar convites de usuários PF para empresas
    """
    STATUS_CHOICES = [
        ('pending', 'Pendente'),
        ('accepted', 'Aceito'),
        ('rejected', 'Recusado'),
        ('expired', 'Expirado'),
    ]

    email_convidado = models.EmailField(
        'Email do Convidado',
        help_text='Email do usuário PF convidado'
    )
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name='convites',
        verbose_name='Empresa'
    )
    convidado = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='convites_recebidos',
        verbose_name='Usuário Convidado'
    )
    status = models.CharField(
        'Status',
        max_length=10,
        choices=STATUS_CHOICES,
        default='pending',
        help_text='Status atual do convite'
    )
    data_envio = models.DateTimeField(
        'Data de Envio',
        auto_now_add=True,
        help_text='Data em que o convite foi enviado'
    )
    data_resposta = models.DateTimeField(
        'Data de Resposta',
        null=True,
        blank=True,
        help_text='Data em que o convite foi respondido'
    )
    data_expiracao = models.DateTimeField(
        'Data de Expiração',
        null=True,
        blank=True,
        help_text='Data em que o convite expira'
    )

    class Meta:
        verbose_name = 'Convite de Usuário'
        verbose_name_plural = 'Convites de Usuários'
        ordering = ['-data_envio']

    def __str__(self):
        return f'Convite para {self.email_convidado} - {self.empresa.nome_fantasia}'

    def aceitar(self, user):
        """
        Aceita o convite e cria o vínculo entre usuário e empresa
        """
        if self.status != 'pending':
            raise ValueError('Apenas convites pendentes podem ser aceitos')
        
        if user.user_type != 'PF':
            raise ValueError('Apenas usuários PF podem aceitar convites')
        
        # Cria o vínculo entre usuário e empresa
        UserCompanyLink.objects.create(
            user=user,
            empresa=self.empresa
        )
        
        # Atualiza o status do convite
        self.status = 'accepted'
        self.convidado = user
        self.data_resposta = timezone.now()
        self.save()

    def recusar(self, user):
        """
        Recusa o convite
        """
        if self.status != 'pending':
            raise ValueError('Apenas convites pendentes podem ser recusados')
        
        if user.user_type != 'PF':
            raise ValueError('Apenas usuários PF podem recusar convites')
        
        self.status = 'rejected'
        self.convidado = user
        self.data_resposta = timezone.now()
        self.save()
