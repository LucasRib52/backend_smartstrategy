from django.db import models
from django.contrib.auth import get_user_model
from empresas.models import Empresa
from django.utils import timezone

User = get_user_model()

class NotificacaoAdmin(models.Model):
    """
    Modelo para notificações do sistema para administradores
    """
    TIPO_CHOICES = [
        ('usuario_criado', 'Usuário PF Criado'),
        ('empresa_criada', 'Empresa Criada'),
        ('plano_expirado', 'Plano Expirado'),
        ('plano_renovado', 'Plano Renovado'),
        ('empresa_bloqueada', 'Empresa Bloqueada'),
        ('empresa_ativada', 'Empresa Ativada'),
        ('pagamento_recebido', 'Pagamento Recebido'),
        ('assinatura_criada', 'Assinatura Criada'),
        ('assinatura_cancelada', 'Assinatura Cancelada'),
        ('sistema', 'Sistema'),
    ]

    PRIORIDADE_CHOICES = [
        ('baixa', 'Baixa'),
        ('media', 'Média'),
        ('alta', 'Alta'),
        ('critica', 'Crítica'),
    ]

    STATUS_CHOICES = [
        ('nao_lida', 'Não Lida'),
        ('lida', 'Lida'),
        ('arquivada', 'Arquivada'),
    ]

    tipo = models.CharField(
        'Tipo',
        max_length=20,
        choices=TIPO_CHOICES,
        help_text='Tipo da notificação'
    )
    
    titulo = models.CharField(
        'Título',
        max_length=200,
        help_text='Título da notificação'
    )
    
    mensagem = models.TextField(
        'Mensagem',
        help_text='Mensagem detalhada da notificação'
    )
    
    prioridade = models.CharField(
        'Prioridade',
        max_length=10,
        choices=PRIORIDADE_CHOICES,
        default='media',
        help_text='Prioridade da notificação'
    )
    
    status = models.CharField(
        'Status',
        max_length=10,
        choices=STATUS_CHOICES,
        default='nao_lida',
        help_text='Status da notificação'
    )
    
    # Campos opcionais para referenciar objetos relacionados
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notificacoes_admin',
        verbose_name='Empresa Relacionada'
    )
    
    usuario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notificacoes_admin',
        verbose_name='Usuário Relacionado'
    )
    
    # Dados adicionais em JSON
    dados_extras = models.JSONField(
        'Dados Extras',
        null=True,
        blank=True,
        help_text='Dados adicionais da notificação'
    )
    
    criado_em = models.DateTimeField(
        'Criado em',
        auto_now_add=True,
        help_text='Data de criação da notificação'
    )
    
    lida_em = models.DateTimeField(
        'Lida em',
        null=True,
        blank=True,
        help_text='Data em que a notificação foi lida'
    )

    class Meta:
        verbose_name = 'Notificação Admin'
        verbose_name_plural = 'Notificações Admin'
        ordering = ['-criado_em']

    def __str__(self):
        return f'{self.tipo}: {self.titulo}'

    def marcar_como_lida(self):
        """Marca a notificação como lida"""
        if self.status == 'nao_lida':
            self.status = 'lida'
            self.lida_em = timezone.now()
            self.save()

    def arquivar(self):
        """Arquiva a notificação"""
        self.status = 'arquivada'
        self.save()

    @classmethod
    def criar_notificacao(cls, tipo, titulo, mensagem, prioridade='media', empresa=None, usuario=None, dados_extras=None):
        """Método de classe para criar notificações facilmente"""
        return cls.objects.create(
            tipo=tipo,
            titulo=titulo,
            mensagem=mensagem,
            prioridade=prioridade,
            empresa=empresa,
            usuario=usuario,
            dados_extras=dados_extras or {}
        )
