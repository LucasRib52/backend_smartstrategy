from django.db import models
from django.utils import timezone


class AsaasWebhook(models.Model):
    """
    Modelo para armazenar webhooks recebidos do Asaas
    """
    EVENT_TYPE_CHOICES = [
        ('SUBSCRIPTION_CREATED', 'Assinatura Criada'),
        ('SUBSCRIPTION_ACTIVATED', 'Assinatura Ativada'),
        ('SUBSCRIPTION_CANCELLED', 'Assinatura Cancelada'),
        ('SUBSCRIPTION_DELETED', 'Assinatura Deletada'),
        ('SUBSCRIPTION_UPDATED', 'Assinatura Atualizada'),
        ('SUBSCRIPTION_INACTIVATED', 'Assinatura Inativada'),
        ('PAYMENT_RECEIVED', 'Pagamento Recebido'),
        ('PAYMENT_OVERDUE', 'Pagamento em Atraso'),
        ('PAYMENT_DELETED', 'Pagamento Deletado'),
        ('PAYMENT_CONFIRMED', 'Pagamento Confirmado'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pendente'),
        ('processed', 'Processado'),
        ('failed', 'Falhou'),
    ]

    event_type = models.CharField(
        'Tipo do Evento',
        max_length=50,
        choices=EVENT_TYPE_CHOICES,
        help_text='Tipo do evento recebido do Asaas'
    )
    
    asaas_id = models.CharField(
        'ID do Asaas',
        max_length=100,
        help_text='ID único do evento no Asaas'
    )
    
    payload = models.JSONField(
        'Dados do Webhook',
        help_text='Dados completos recebidos do webhook'
    )
    
    status = models.CharField(
        'Status',
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        help_text='Status do processamento do webhook'
    )
    
    error_message = models.TextField(
        'Mensagem de Erro',
        blank=True,
        null=True,
        help_text='Mensagem de erro se o processamento falhou'
    )
    
    processed_at = models.DateTimeField(
        'Processado em',
        null=True,
        blank=True,
        help_text='Data/hora em que foi processado'
    )
    
    created_at = models.DateTimeField(
        'Criado em',
        auto_now_add=True,
        help_text='Data/hora de criação do registro'
    )

    class Meta:
        verbose_name = 'Webhook Asaas'
        verbose_name_plural = 'Webhooks Asaas'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['event_type'], name='webhook_event_idx'),
            models.Index(fields=['status'], name='webhook_status_idx'),
            models.Index(fields=['created_at'], name='webhook_created_idx'),
        ]

    def __str__(self):
        return f"{self.get_event_type_display()} - {self.asaas_id}"

    def mark_as_processed(self):
        """Marca o webhook como processado"""
        self.status = 'processed'
        self.processed_at = timezone.now()
        self.save(update_fields=['status', 'processed_at'])

    def mark_as_failed(self, error_message):
        """Marca o webhook como falhou"""
        self.status = 'failed'
        self.error_message = error_message
        self.save(update_fields=['status', 'error_message'])

    @classmethod
    def create_from_payload(cls, event_type, asaas_id, payload):
        """Cria um novo webhook a partir dos dados recebidos"""
        return cls.objects.create(
            event_type=event_type,
            asaas_id=asaas_id,
            payload=payload
        )
