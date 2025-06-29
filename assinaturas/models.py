from django.db import models
from django.utils import timezone
from django.conf import settings


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

    def __str__(self):
        return self.nome


class Assinatura(models.Model):
    """Assinatura vinculada a uma empresa."""

    empresa = models.ForeignKey('empresas.Empresa', related_name='assinaturas', on_delete=models.CASCADE)
    plano = models.ForeignKey(Plano, on_delete=models.PROTECT)
    inicio = models.DateTimeField(default=timezone.now)
    fim = models.DateTimeField()
    ativa = models.BooleanField(default=True)
    expirada = models.BooleanField(default=False)
    observacoes = models.TextField(blank=True, null=True, help_text="Observações sobre a assinatura")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-inicio']

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
