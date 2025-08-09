from django.db import models
from django.utils import timezone
from django.conf import settings
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver


class Plano(models.Model):
    """Tabela de planos disponíveis (trial ou pagos)."""

    codigo = models.CharField(max_length=20, unique=True)
    nome = models.CharField(max_length=100)
    preco = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    duracao_dias = models.PositiveIntegerField(
        default=7,
        help_text="Número de dias que a assinatura referente ao plano dura. Para trial, 7 dias por padrão."
    )
    ativo = models.BooleanField(default=True)
    # Integração Asaas
    asaas_product_id = models.CharField(max_length=100, null=True, blank=True)
    asaas_price_id = models.CharField(max_length=100, null=True, blank=True)
    trial_days = models.PositiveIntegerField(default=7)
    auto_renew = models.BooleanField(default=True)
    
    # Permissões de módulos
    acesso_financeiro = models.BooleanField(default=True, help_text="Acesso ao módulo financeiro")
    acesso_marketing = models.BooleanField(default=True, help_text="Acesso ao módulo de marketing")
    acesso_influencer = models.BooleanField(default=False, help_text="Acesso ao módulo influencer")
    acesso_analytics = models.BooleanField(default=True, help_text="Acesso ao módulo de analytics")
    acesso_usuarios = models.BooleanField(default=True, help_text="Acesso ao módulo de usuários")
    acesso_configuracoes = models.BooleanField(default=True, help_text="Acesso ao módulo de configurações")
    acesso_relatorios = models.BooleanField(default=False, help_text="Acesso ao módulo de relatórios")
    acesso_api = models.BooleanField(default=False, help_text="Acesso à API")
    acesso_white_label = models.BooleanField(default=False, help_text="Acesso ao white label")
    acesso_suporte_prioritario = models.BooleanField(default=False, help_text="Suporte prioritário")

    # Vantagens e desvantagens do plano
    vantagens = models.JSONField(
        default=list, 
        blank=True, 
        help_text="Lista de vantagens do plano (ex: ['Suporte 24/7', 'Analytics avançados'])"
    )
    desvantagens = models.JSONField(
        default=list, 
        blank=True, 
        help_text="Lista de limitações do plano (ex: ['Máximo 100 produtos', 'Sem API'])"
    )
    descricao = models.TextField(
        blank=True, 
        null=True,
        help_text="Descrição detalhada do plano"
    )

    def __str__(self):
        return self.nome

    def get_permissoes(self):
        """Retorna dicionário com todas as permissões do plano"""
        return {
            'financeiro': self.acesso_financeiro,
            'marketing': self.acesso_marketing,
            'influencer': self.acesso_influencer,
            'analytics': self.acesso_analytics,
            'usuarios': self.acesso_usuarios,
            'configuracoes': self.acesso_configuracoes,
            'relatorios': self.acesso_relatorios,
            'api': self.acesso_api,
            'white_label': self.acesso_white_label,
            'suporte_prioritario': self.acesso_suporte_prioritario,
        }


# Signal para criar produto no Asaas quando plano for criado/atualizado
@receiver(post_save, sender=Plano)
def create_asaas_product(sender, instance, created, **kwargs):
    """
    Cria produto no Asaas quando plano for criado ou atualizado
    """
    try:
        # Só cria produto no Asaas se o plano for pago (preco > 0)
        if instance.preco > 0 and instance.ativo:
            from asaas.services import AsaasService
            
            asaas_service = AsaasService()
            
            # Se já tem ID do Asaas, atualiza o produto
            if instance.asaas_product_id:
                # Atualiza produto existente
                product_data = {
                    'name': instance.nome,
                    'description': f"Plano {instance.nome} - SmartStrategy",
                    'price': float(instance.preco)
                }
                asaas_service._make_request('PUT', f'products/{instance.asaas_product_id}', product_data)
            else:
                # Cria novo produto
                asaas_service.create_product(instance)
                
    except Exception as e:
        # Log do erro mas não falha a operação
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Erro ao criar/atualizar produto no Asaas para plano {instance.nome}: {str(e)}")


class Assinatura(models.Model):
    """Assinatura vinculada a uma empresa."""

    empresa = models.ForeignKey('empresas.Empresa', related_name='assinaturas', on_delete=models.CASCADE)
    plano = models.ForeignKey(Plano, on_delete=models.PROTECT)
    inicio = models.DateTimeField(default=timezone.now)
    fim = models.DateTimeField()
    # Integração Asaas
    asaas_subscription_id = models.CharField(max_length=100, null=True, blank=True)
    asaas_customer_id = models.CharField(max_length=100, null=True, blank=True)
    PAYMENT_STATUS_CHOICES = [
        ('PENDING', 'Pendente'),
        ('CONFIRMED', 'Confirmado'),
        ('OVERDUE', 'Em Atraso'),
        ('CANCELLED', 'Cancelado'),
    ]
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='PENDING')
    next_payment_date = models.DateField(null=True, blank=True)
    trial_end_date = models.DateTimeField(null=True, blank=True)
    ativa = models.BooleanField(default=True)
    expirada = models.BooleanField(default=False)
    observacoes = models.TextField(blank=True, null=True, help_text="Observações sobre a assinatura")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-inicio']
        indexes = [
            models.Index(fields=['empresa', 'ativa', 'expirada'], name='assin_empresa_ativa_exp'),
            models.Index(fields=['asaas_subscription_id'], name='assin_asaas_sub_idx'),
            models.Index(fields=['payment_status'], name='assin_pay_status_idx'),
            models.Index(fields=['fim'], name='assin_fim_idx'),
        ]

    def __str__(self):
        return f"{self.empresa} – {self.plano.nome}"

    def marcar_como_expirada(self):
        self.ativa = False
        self.expirada = True
        self.save(update_fields=['ativa', 'expirada'])


class HistoricoPagamento(models.Model):
    """Histórico de todas as mudanças em pagamentos/assinaturas."""
    
    TIPO_CHOICES = [
        ('CRIACAO', 'Criação'),
        ('ATIVACAO', 'Ativação'),
        ('EXPIRACAO', 'Expiração'),
        ('REATIVACAO', 'Reativação'),
        ('TROCA_PLANO', 'Troca de Plano'),
        ('EXTENSAO', 'Extensão de Prazo'),
        ('BLOQUEIO', 'Bloqueio'),
        ('DESBLOQUEIO', 'Desbloqueio'),
        ('CANCELAMENTO', 'Cancelamento'),
    ]

    assinatura = models.ForeignKey(Assinatura, related_name='historico', on_delete=models.CASCADE)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    descricao = models.TextField()
    plano_anterior = models.ForeignKey(Plano, on_delete=models.SET_NULL, null=True, blank=True, related_name='historico_anterior')
    plano_novo = models.ForeignKey(Plano, on_delete=models.SET_NULL, null=True, blank=True, related_name='historico_novo')
    data_inicio_anterior = models.DateTimeField(null=True, blank=True)
    data_fim_anterior = models.DateTimeField(null=True, blank=True)
    data_inicio_nova = models.DateTimeField(null=True, blank=True)
    data_fim_nova = models.DateTimeField(null=True, blank=True)
    dias_adicional = models.PositiveIntegerField(null=True, blank=True, help_text="Dias adicionados na extensão")
    valor_anterior = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    valor_novo = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    usuario_admin = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, help_text="Admin que fez a alteração")
    criado_em = models.DateTimeField(auto_now_add=True)
    observacoes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-criado_em']
        verbose_name = 'Histórico de Pagamento'
        verbose_name_plural = 'Históricos de Pagamento'

    def __str__(self):
        return f"{self.assinatura.empresa} - {self.get_tipo_display()} - {self.criado_em.strftime('%d/%m/%Y %H:%M')}"
