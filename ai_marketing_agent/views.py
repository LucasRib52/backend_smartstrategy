from django.shortcuts import render
import os
import logging
from datetime import datetime, timedelta, date
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.db import transaction, models
from django.utils import timezone
from rest_framework import status, viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser

from .models import MarketingData, FileUpload
from .serializers import (
    MarketingDataSerializer, FileUploadSerializer, FileUploadCreateSerializer,
    ProcessingResultSerializer, AIProcessingRequestSerializer
)
from .ai_agent import AIMarketingAgent
from venda.models import Venda

logger = logging.getLogger(__name__)

class MarketingDataViewSet(viewsets.ModelViewSet):
    """ViewSet para dados de marketing processados pela IA"""
    
    serializer_class = MarketingDataSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Filtra dados por empresa do usuário"""
        queryset = MarketingData.objects.all()
        
        # Filtra por empresa se o usuário tiver uma empresa atual
        if hasattr(self.request.user, 'empresa_atual') and self.request.user.empresa_atual:
            queryset = queryset.filter(empresa=self.request.user.empresa_atual)
        
        # Filtros adicionais
        platform = self.request.query_params.get('platform', None)
        if platform:
            queryset = queryset.filter(platform=platform)
        
        campaign_name = self.request.query_params.get('campaign_name', None)
        if campaign_name:
            queryset = queryset.filter(campaign_name__icontains=campaign_name)
        
        date_from = self.request.query_params.get('date_from', None)
        if date_from:
            queryset = queryset.filter(data__gte=date_from)
        
        date_to = self.request.query_params.get('date_to', None)
        if date_to:
            queryset = queryset.filter(data__lte=date_to)
        
        return queryset.order_by('-data', 'campaign_name')
    
    @action(detail=False, methods=['get'])
    def platforms(self, request):
        """Retorna lista de plataformas disponíveis"""
        platforms = MarketingData.objects.values_list('platform', flat=True).distinct()
        return Response({
            'platforms': list(platforms)
        })
    
    @action(detail=False, methods=['get'])
    def campaigns(self, request):
        """Retorna lista de campanhas disponíveis"""
        campaigns = MarketingData.objects.values_list('campaign_name', flat=True).distinct()
        return Response({
            'campaigns': list(campaigns)
        })
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Retorna resumo dos dados de marketing"""
        queryset = self.get_queryset()
        
        # Estatísticas gerais
        total_records = queryset.count()
        total_cost = queryset.aggregate(total=models.Sum('cost'))['total'] or 0
        total_clicks = queryset.aggregate(total=models.Sum('clicks'))['total'] or 0
        total_impressions = queryset.aggregate(total=models.Sum('impressions'))['total'] or 0
        total_conversions = queryset.aggregate(total=models.Sum('conversions'))['total'] or 0
        
        # Médias
        avg_ctr = queryset.aggregate(avg=models.Avg('ctr'))['avg'] or 0
        avg_cpc = queryset.aggregate(avg=models.Avg('cpc'))['avg'] or 0
        avg_cpm = queryset.aggregate(avg=models.Avg('cpm'))['avg'] or 0
        
        return Response({
            'total_records': total_records,
            'total_cost': float(total_cost),
            'total_clicks': total_clicks,
            'total_impressions': total_impressions,
            'total_conversions': total_conversions,
            'avg_ctr': float(avg_ctr),
            'avg_cpc': float(avg_cpc),
            'avg_cpm': float(avg_cpm)
        })

class FileUploadViewSet(viewsets.ModelViewSet):
    """ViewSet para upload e processamento de arquivos"""
    
    serializer_class = FileUploadSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    
    def get_queryset(self):
        """Filtra uploads por empresa do usuário"""
        queryset = FileUpload.objects.all()
        
        # Filtra por empresa se o usuário tiver uma empresa atual
        if hasattr(self.request.user, 'empresa_atual') and self.request.user.empresa_atual:
            queryset = queryset.filter(empresa=self.request.user.empresa_atual)
        
        return queryset.order_by('-uploaded_at')
    
    def get_serializer_class(self):
        """Retorna serializer apropriado baseado na ação"""
        if self.action == 'create':
            return FileUploadCreateSerializer
        return FileUploadSerializer
    
    @action(detail=True, methods=['post'])
    def process(self, request, pk=None):
        """Processa um arquivo usando IA"""
        try:
            file_upload = self.get_object()
            
            # Verifica se já foi processado
            if file_upload.status == 'completed' and not request.data.get('force_reprocess', False):
                return Response({
                    'success': False,
                    'message': 'Arquivo já foi processado. Use force_reprocess=true para reprocessar.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Atualiza status para processando
            file_upload.status = 'processing'
            file_upload.save()
            
            # Processa o arquivo
            result = self._process_file_with_ai(file_upload)
            
            return Response(result)
            
        except Exception as e:
            logger.error(f"Erro ao processar arquivo: {str(e)}")
            return Response({
                'success': False,
                'message': f'Erro ao processar arquivo: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def upload_and_process(self, request):
        """Upload e processamento em uma única operação"""
        try:
            preview_only_raw = request.data.get('preview_only', 'false')
            preview_only = str(preview_only_raw).lower() in ['true', '1', 'yes']
            # Cria o upload
            serializer = FileUploadCreateSerializer(data=request.data, context={'request': request})
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            file_upload = serializer.save()
            
            # Processa imediatamente
            result = self._process_file_with_ai(file_upload, save=not preview_only)
            
            return Response(result)
            
        except Exception as e:
            logger.error(f"Erro no upload e processamento: {str(e)}")
            return Response({
                'success': False,
                'message': f'Erro no upload e processamento: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _process_file_with_ai(self, file_upload: FileUpload, save: bool = True) -> dict:
        """Processa arquivo usando o agente de IA"""
        try:
            # Inicializa o agente de IA (ele próprio pega a chave do settings ou variável de ambiente)
            agent = AIMarketingAgent()
            
            # Salva arquivo temporariamente
            file_path = default_storage.path(file_upload.file.name)
            
            # Processa com IA
            empresa_id = file_upload.empresa.id if file_upload.empresa else None
            result = agent.process_file(
                file_path=file_path,
                user_id=file_upload.user.id,
                empresa_id=empresa_id
            )
            
            if result['success'] and save:
                # Salva os dados no banco
                saved_data = self._save_processed_data(
                    result['data'], 
                    file_upload.user, 
                    file_upload.empresa,
                    file_upload.file_name
                )
                
                # Atualiza status do upload
                file_upload.status = 'completed'
                file_upload.records_processed = result['records_count']
                file_upload.records_created = saved_data['created']
                file_upload.records_updated = saved_data['updated']
                file_upload.processed_at = timezone.now()
                file_upload.save()
                
                return {
                    'success': True,
                    'message': f'Processamento concluído com sucesso! {saved_data["created"]} registros criados, {saved_data["updated"]} atualizados.',
                    'records_processed': result['records_count'],
                    'records_created': saved_data['created'],
                    'records_updated': saved_data['updated'],
                    'data_preview': result['data'][:5] if result['data'] else []
                }
            elif not save and result['success']:
                # Apenas preview, não salva nada no banco
                return {
                    'success': True,
                    'message': 'Pré-visualização gerada com sucesso.',
                    'records_processed': result['records_count'],
                    'records_created': 0,
                    'records_updated': 0,
                    'data_preview': result['data'][:5] if result['data'] else []
                }
            else:
                # Atualiza status para falhou
                file_upload.status = 'failed'
                file_upload.error_message = result.get('error', 'Erro desconhecido')
                file_upload.save()
                
                return {
                    'success': False,
                    'message': f'Erro no processamento: {result.get("error", "Erro desconhecido")}',
                    'records_processed': 0,
                    'records_created': 0,
                    'records_updated': 0
                }
                
        except Exception as e:
            # Atualiza status para falhou
            file_upload.status = 'failed'
            file_upload.error_message = str(e)
            file_upload.save()
            
            logger.error(f"Erro ao processar arquivo {file_upload.file_name}: {str(e)}")
            raise
    
    @transaction.atomic
    def _save_processed_data(self, data: list, user, empresa, source_file: str) -> dict:
        """Salva dados processados no banco"""
        created_count = 0
        updated_count = 0
        
        for record in data:
            try:
                # Converte string de data para objeto date
                if isinstance(record['data'], str):
                    record['data'] = datetime.strptime(record['data'], '%Y-%m-%d').date()
                
                # Tenta encontrar registro existente
                existing = MarketingData.objects.filter(
                    data=record['data'],
                    campaign_name=record['campaign_name'],
                    platform=record['platform'],
                    empresa=empresa
                ).first()
                
                if existing:
                    # Atualiza registro existente
                    for field, value in record.items():
                        if hasattr(existing, field):
                            setattr(existing, field, value)
                    existing.source_file = source_file
                    existing.save()
                    updated_count += 1
                else:
                    # Cria novo registro
                    MarketingData.objects.create(
                        user=user,
                        empresa=empresa,
                        source_file=source_file,
                        **record
                    )
                    created_count += 1
                    
                # ---- Agrupa por semana (ano + semana ISO) ----
                try:
                    date_obj = record['data'] if isinstance(record['data'], date) else datetime.strptime(record['data'], '%Y-%m-%d').date()
                except Exception:
                    date_obj = datetime.now().date()

                iso_calendar = date_obj.isocalendar()
                week_number = str(iso_calendar.week)
                year_number = iso_calendar.year

                venda_defaults = {
                    'data': date_obj - timedelta(days=date_obj.weekday()),  # define como segunda-feira da semana
                    'invest_realizado': record.get('cost', 0) or 0,
                    'invest_projetado': record.get('cost', 0) or 0,
                    'vendas_google': record.get('cost', 0) or 0,
                    'vendas_instagram': 0,
                    'vendas_facebook': 0,
                    'fat_proj': 0,
                    'fat_camp_realizado': 0,
                    'fat_geral': 0,
                    'leads': record.get('clicks', 0) or 0,
                    'clientes_novos': record.get('conversions', 0) or 0,
                    'clientes_recorrentes': 0,
                    'conversoes': record.get('conversions', 0) or 0,
                    'ticket_medio_realizado': 0,
                }

                venda_obj, created_flag = Venda.objects.get_or_create(
                    empresa=empresa,
                    ano=year_number,
                    semana=week_number,
                    defaults=venda_defaults
                )

                if not created_flag:
                    # Soma métricas
                    for key, value in venda_defaults.items():
                        if isinstance(value, (int, float)):
                            atual = getattr(venda_obj, key, 0) or 0
                            setattr(venda_obj, key, atual + value)
                    venda_obj.save()

            except Exception as e:
                logger.error(f"Erro ao salvar registro: {record} - {str(e)}")
                continue
        
        return {
            'created': created_count,
            'updated': updated_count
        }
    
    @action(detail=False, methods=['get'])
    def supported_formats(self, request):
        """Retorna formatos de arquivo suportados"""
        return Response({
            'supported_formats': [
                {
                    'type': 'Planilhas',
                    'extensions': ['.csv', '.xlsx', '.xls'],
                    'description': 'Arquivos CSV e Excel com dados de marketing'
                },
                {
                    'type': 'Documentos',
                    'extensions': ['.pdf'],
                    'description': 'Relatórios PDF com métricas de campanha'
                },
                {
                    'type': 'Imagens',
                    'extensions': ['.png', '.jpg', '.jpeg'],
                    'description': 'Screenshots de dashboards e relatórios'
                }
            ]
        })
