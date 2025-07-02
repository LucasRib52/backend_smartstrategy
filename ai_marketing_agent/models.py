from django.db import models
from empresas.models import Empresa
from django.conf import settings
from datetime import date

class MarketingData(models.Model):
    """Modelo para armazenar dados de marketing processados pela IA"""
    
    # Relacionamentos
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='marketing_data', null=True, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='marketing_data_uploads')
    
    # Campos de Data e Informações Temporais
    data = models.DateField("Data")
    mes = models.CharField("Mês", max_length=20, blank=True)
    ano = models.IntegerField("Ano", blank=True, null=True)
    semana = models.CharField("Semana", max_length=10, blank=True)
    
    # Campos de Campanha
    campaign_name = models.CharField("Nome da Campanha", max_length=200)
    platform = models.CharField("Plataforma", max_length=50, choices=[
        ('google', 'Google Ads'),
        ('facebook', 'Facebook Ads'),
        ('instagram', 'Instagram Ads'),
        ('tiktok', 'TikTok Ads'),
        ('linkedin', 'LinkedIn Ads'),
        ('other', 'Outros'),
    ])
    
    # Métricas de Performance
    clicks = models.IntegerField("Cliques", default=0)
    impressions = models.IntegerField("Impressões", default=0)
    cost = models.DecimalField("Custo (R$)", max_digits=10, decimal_places=2, default=0)
    conversions = models.IntegerField("Conversões", default=0)
    
    # Métricas Calculadas
    ctr = models.DecimalField("CTR (%)", max_digits=5, decimal_places=2, blank=True, null=True)
    cpc = models.DecimalField("CPC (R$)", max_digits=10, decimal_places=2, blank=True, null=True)
    cpm = models.DecimalField("CPM (R$)", max_digits=10, decimal_places=2, blank=True, null=True)
    conversion_rate = models.DecimalField("Taxa de Conversão (%)", max_digits=5, decimal_places=2, blank=True, null=True)
    
    # Informações do Processamento
    source_file = models.CharField("Arquivo Original", max_length=255, blank=True)
    processed_at = models.DateTimeField("Processado em", auto_now_add=True)
    confidence_score = models.DecimalField("Confiança da IA", max_digits=3, decimal_places=2, blank=True, null=True)
    
    # Campos de Auditoria
    created_at = models.DateTimeField("Criado em", auto_now_add=True)
    updated_at = models.DateTimeField("Atualizado em", auto_now=True)
    
    class Meta:
        unique_together = ['data', 'campaign_name', 'platform', 'empresa']
        ordering = ['-data', 'campaign_name']
        verbose_name = "Dado de Marketing"
        verbose_name_plural = "Dados de Marketing"
    
    def save(self, *args, **kwargs):
        # Atualiza campos temporais
        if self.data:
            self.semana = str(self.data.isocalendar().week)
            # Nome do mês em português
            month_pt = {
                1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril', 5: 'Maio', 6: 'Junho',
                7: 'Julho', 8: 'Agosto', 9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'
            }
            self.mes = month_pt.get(self.data.month, self.data.month)
            self.ano = self.data.year
        
        # Calcula métricas
        if self.impressions and self.impressions > 0:
            self.ctr = (self.clicks / self.impressions) * 100
        
        if self.clicks and self.clicks > 0:
            self.cpc = self.cost / self.clicks
        
        if self.impressions and self.impressions > 0:
            self.cpm = (self.cost / self.impressions) * 1000
        
        if self.clicks and self.clicks > 0:
            self.conversion_rate = (self.conversions / self.clicks) * 100
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.data.strftime('%d/%m/%Y')} - {self.campaign_name} ({self.platform})"

class FileUpload(models.Model):
    """Modelo para rastrear arquivos enviados para processamento"""
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='file_uploads')
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='file_uploads', null=True, blank=True)
    
    file = models.FileField("Arquivo", upload_to='marketing_uploads/')
    file_name = models.CharField("Nome do Arquivo", max_length=255)
    file_size = models.BigIntegerField("Tamanho do Arquivo (bytes)")
    file_type = models.CharField("Tipo do Arquivo", max_length=100)
    
    # Status do processamento
    STATUS_CHOICES = [
        ('pending', 'Pendente'),
        ('processing', 'Processando'),
        ('completed', 'Concluído'),
        ('failed', 'Falhou'),
    ]
    status = models.CharField("Status", max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Resultados do processamento
    records_processed = models.IntegerField("Registros Processados", default=0)
    records_created = models.IntegerField("Registros Criados", default=0)
    records_updated = models.IntegerField("Registros Atualizados", default=0)
    error_message = models.TextField("Mensagem de Erro", blank=True)
    
    # Timestamps
    uploaded_at = models.DateTimeField("Enviado em", auto_now_add=True)
    processed_at = models.DateTimeField("Processado em", null=True, blank=True)
    
    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = "Upload de Arquivo"
        verbose_name_plural = "Uploads de Arquivos"
    
    def __str__(self):
        return f"{self.file_name} - {self.get_status_display()}"
