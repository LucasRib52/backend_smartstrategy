from rest_framework import serializers
from .models import MarketingData, FileUpload
from datetime import datetime

class MarketingDataSerializer(serializers.ModelSerializer):
    """Serializer para dados de marketing"""
    
    platform_display = serializers.CharField(source='get_platform_display', read_only=True)
    data_formatted = serializers.SerializerMethodField()
    
    class Meta:
        model = MarketingData
        fields = [
            'id', 'data', 'data_formatted', 'mes', 'ano', 'semana',
            'campaign_name', 'platform', 'platform_display',
            'clicks', 'impressions', 'cost', 'conversions',
            'ctr', 'cpc', 'cpm', 'conversion_rate',
            'source_file', 'processed_at', 'confidence_score',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'mes', 'ano', 'semana', 'ctr', 'cpc', 'cpm', 'conversion_rate',
            'processed_at', 'created_at', 'updated_at'
        ]
    
    def get_data_formatted(self, obj):
        """Retorna a data formatada"""
        if obj.data:
            return obj.data.strftime('%d/%m/%Y')
        return None

class FileUploadSerializer(serializers.ModelSerializer):
    """Serializer para upload de arquivos"""
    
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    file_size_mb = serializers.SerializerMethodField()
    uploaded_at_formatted = serializers.SerializerMethodField()
    processed_at_formatted = serializers.SerializerMethodField()
    
    class Meta:
        model = FileUpload
        fields = [
            'id', 'file', 'file_name', 'file_size', 'file_size_mb', 'file_type',
            'status', 'status_display', 'records_processed', 'records_created', 
            'records_updated', 'error_message', 'uploaded_at', 'uploaded_at_formatted',
            'processed_at', 'processed_at_formatted'
        ]
        read_only_fields = [
            'file_name', 'file_size', 'file_type', 'status', 'records_processed',
            'records_created', 'records_updated', 'error_message', 'uploaded_at', 'processed_at'
        ]
    
    def get_file_size_mb(self, obj):
        """Retorna o tamanho do arquivo em MB"""
        if obj.file_size:
            return round(obj.file_size / (1024 * 1024), 2)
        return 0
    
    def get_uploaded_at_formatted(self, obj):
        """Retorna a data de upload formatada"""
        if obj.uploaded_at:
            return obj.uploaded_at.strftime('%d/%m/%Y %H:%M')
        return None
    
    def get_processed_at_formatted(self, obj):
        """Retorna a data de processamento formatada"""
        if obj.processed_at:
            return obj.processed_at.strftime('%d/%m/%Y %H:%M')
        return None
    
    def create(self, validated_data):
        """Cria um novo upload de arquivo"""
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['user'] = request.user
            
            # Pega a empresa do usuário se disponível
            if hasattr(request.user, 'empresa_atual'):
                validated_data['empresa'] = request.user.empresa_atual
        
        # Salva o arquivo
        file_obj = validated_data['file']
        validated_data['file_name'] = file_obj.name
        validated_data['file_size'] = file_obj.size
        validated_data['file_type'] = file_obj.content_type
        
        return super().create(validated_data)

class FileUploadCreateSerializer(serializers.ModelSerializer):
    """Serializer simplificado para criação de upload"""
    
    class Meta:
        model = FileUpload
        fields = ['file']
    
    def create(self, validated_data):
        """Cria um novo upload de arquivo"""
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['user'] = request.user
            
            # Pega a empresa do usuário se disponível
            if hasattr(request.user, 'empresa_atual'):
                validated_data['empresa'] = request.user.empresa_atual
        
        # Salva o arquivo
        file_obj = validated_data['file']
        validated_data['file_name'] = file_obj.name
        validated_data['file_size'] = file_obj.size
        validated_data['file_type'] = file_obj.content_type
        
        return super().create(validated_data)

class ProcessingResultSerializer(serializers.Serializer):
    """Serializer para resultados do processamento"""
    
    success = serializers.BooleanField()
    message = serializers.CharField()
    records_processed = serializers.IntegerField()
    records_created = serializers.IntegerField()
    records_updated = serializers.IntegerField()
    errors = serializers.ListField(child=serializers.CharField(), required=False)
    data_preview = serializers.ListField(required=False)

class AIProcessingRequestSerializer(serializers.Serializer):
    """Serializer para requisições de processamento"""
    
    file_id = serializers.IntegerField()
    force_reprocess = serializers.BooleanField(default=False) 