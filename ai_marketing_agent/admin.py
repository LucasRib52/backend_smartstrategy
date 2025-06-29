from django.contrib import admin
from .models import MarketingData, FileUpload

@admin.register(MarketingData)
class MarketingDataAdmin(admin.ModelAdmin):
    list_display = [
        'data', 'campaign_name', 'platform', 'clicks', 'impressions', 
        'cost', 'conversions', 'ctr', 'empresa', 'user'
    ]
    list_filter = ['platform', 'data', 'empresa', 'user']
    search_fields = ['campaign_name', 'user__username', 'empresa__nome']
    readonly_fields = ['ctr', 'cpc', 'cpm', 'conversion_rate', 'processed_at', 'created_at', 'updated_at']
    date_hierarchy = 'data'
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('empresa', 'user', 'data', 'campaign_name', 'platform')
        }),
        ('Métricas de Performance', {
            'fields': ('clicks', 'impressions', 'cost', 'conversions')
        }),
        ('Métricas Calculadas', {
            'fields': ('ctr', 'cpc', 'cpm', 'conversion_rate'),
            'classes': ('collapse',)
        }),
        ('Informações do Processamento', {
            'fields': ('source_file', 'confidence_score', 'processed_at'),
            'classes': ('collapse',)
        }),
        ('Auditoria', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(FileUpload)
class FileUploadAdmin(admin.ModelAdmin):
    list_display = [
        'file_name', 'status', 'records_processed', 'records_created', 
        'records_updated', 'user', 'empresa', 'uploaded_at'
    ]
    list_filter = ['status', 'file_type', 'uploaded_at', 'empresa', 'user']
    search_fields = ['file_name', 'user__username', 'empresa__nome']
    readonly_fields = [
        'file_name', 'file_size', 'file_type', 'uploaded_at', 'processed_at',
        'records_processed', 'records_created', 'records_updated'
    ]
    date_hierarchy = 'uploaded_at'
    
    fieldsets = (
        ('Informações do Arquivo', {
            'fields': ('file', 'file_name', 'file_size', 'file_type')
        }),
        ('Usuário e Empresa', {
            'fields': ('user', 'empresa')
        }),
        ('Status do Processamento', {
            'fields': ('status', 'error_message')
        }),
        ('Resultados', {
            'fields': ('records_processed', 'records_created', 'records_updated'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('uploaded_at', 'processed_at'),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        """Desabilita criação manual no admin"""
        return False
