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
from decimal import Decimal
from typing import Dict, Tuple, Any, Optional

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
            forced_platform = request.data.get('forced_platform')
            # Cria o upload
            serializer = FileUploadCreateSerializer(data=request.data, context={'request': request})
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            file_upload = serializer.save()
            
            # Processa imediatamente
            result = self._process_file_with_ai(file_upload, save=not preview_only, forced_platform=forced_platform)
            
            return Response(result)
            
        except Exception as e:
            logger.error(f"Erro no upload e processamento: {str(e)}")
            return Response({
                'success': False,
                'message': f'Erro no upload e processamento: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _process_file_with_ai(self, file_upload: FileUpload, save: bool = True, forced_platform: Optional[str] = None) -> dict:
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
            
            # Se forçada plataforma, valida e/ou aplica override
            if forced_platform:
                forced_platform = forced_platform.lower()
                valid_pf = ['google', 'facebook', 'instagram']
                if forced_platform not in valid_pf:
                    forced_platform = None

            if forced_platform:
                # Se qualquer registro já indicar plataforma diferente de forced_platform (e não 'other') lançamos erro.
                mismatches = [rec for rec in result.get('data', []) if rec.get('platform') not in [forced_platform, 'other', None]]
                if mismatches:
                    return {
                        'success': False,
                        'message': f'Arquivo parece pertencer a outra plataforma (detectado "{mismatches[0].get("platform")}"). Use o painel correto.',
                        'records_processed': 0,
                        'records_created': 0,
                        'records_updated': 0
                    }
                # Override plataforma para todos os registros
                for rec in result['data']:
                    rec['platform'] = forced_platform
            
            if result['success'] and save:
                # Salva os dados no banco
                saved_data = self._save_processed_data(
                    result['data'], 
                    file_upload.user, 
                    file_upload.empresa,
                    file_upload.file_name,
                    forced_platform=forced_platform
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
    def _save_processed_data(self, data: list, user, empresa, source_file: str, forced_platform: Optional[str] = None) -> dict:
        """Salva dados processados no banco
        - Cria/atualiza registros de MarketingData
        - Consolida campanhas que pertençam à mesma semana em um único registro de Venda,
          somando seus valores de investimento, leads e conversões.
        """
        created_count = 0
        updated_count = 0

        from decimal import Decimal as _Dec  # Import local para uso interno
        from datetime import date, datetime, timedelta  # Garantir que o escopo local tenha date/datetime

        # ------------------------------------------------------------------
        # 1) Consolida registros duplicados (mesma data + campanha + plataforma)
        # ------------------------------------------------------------------
        aggregated: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
        for rec in data:
            # Força plataforma se necessário
            if forced_platform:
                rec = rec.copy()
                rec['platform'] = forced_platform
            key = (rec['data'], rec['campaign_name'], rec['platform'])
            if key not in aggregated:
                aggregated[key] = rec.copy()
            else:
                # Soma métricas numéricas
                for field in ['clicks', 'impressions', 'conversions']:
                    aggregated[key][field] = (aggregated[key].get(field, 0) or 0) + (rec.get(field, 0) or 0)
                # Custo
                aggregated[key]['cost'] = (aggregated[key].get('cost', 0) or 0) + (rec.get('cost', 0) or 0)

        # ------------------------------------------------------------------
        # 2) Salva MarketingData e acumula totais semanais para Venda
        # ------------------------------------------------------------------
        weekly_totals: Dict[Tuple[int, int, str], Dict[str, Any]] = {}

        for record in aggregated.values():
            try:
                # --- Conversão de data e cálculo de semana ---
                if isinstance(record['data'], str):
                    record['data'] = datetime.strptime(record['data'], '%Y-%m-%d').date()

                date_obj: date = record['data']
                iso_calendar = date_obj.isocalendar()
                year_number = iso_calendar[0] if isinstance(iso_calendar, tuple) else iso_calendar.year
                week_number = iso_calendar[1] if isinstance(iso_calendar, tuple) else iso_calendar.week

                plataforma_reg = forced_platform if forced_platform else (record.get('platform') or 'google')

                # ----- Atualiza/acumula weekly_totals -----
                week_key = (year_number, week_number, plataforma_reg)
                wt = weekly_totals.setdefault(
                    week_key,
                    {
                        'data': date_obj,
                        'invest_realizado': _Dec('0'),
                        'leads': 0,
                        'conversoes': 0,
                    }
                )

                # Menor data da semana
                if date_obj < wt['data']:
                    wt['data'] = date_obj
                # Soma métricas
                wt['invest_realizado'] += _Dec(str(record.get('cost', 0) or 0))
                wt['leads'] += int(record.get('clicks', 0) or 0)
                wt['conversoes'] += int(record.get('conversions', 0) or 0)

                # ----- MarketingData: cria ou atualiza -----
                existing = MarketingData.objects.filter(
                    data=record['data'],
                    campaign_name=record['campaign_name'],
                    platform=record['platform'],
                    empresa=empresa
                ).first()

                if existing:
                    # Atualiza registro existente somando métricas
                    numeric_fields = ['clicks', 'impressions', 'conversions']
                    monetary_fields = ['cost']

                    for field, value in record.items():
                        if not hasattr(existing, field):
                            continue
                        current_val = getattr(existing, field)

                        if field in numeric_fields:
                            try:
                                value_int = int(float(value)) if value is not None else 0
                                setattr(existing, field, (current_val or 0) + value_int)
                            except Exception:
                                setattr(existing, field, value)
                        elif field in monetary_fields:
                            try:
                                value_dec = _Dec(str(value)) if value is not None else _Dec('0')
                                setattr(existing, field, (current_val or _Dec('0')) + value_dec)
                            except Exception:
                                setattr(existing, field, value)
                        else:
                            if not current_val:
                                setattr(existing, field, value)
                    existing.source_file = source_file
                    existing.save()
                    updated_count += 1
                else:
                    MarketingData.objects.create(
                        user=user,
                        empresa=empresa,
                        source_file=source_file,
                        **record
                    )
                    created_count += 1

            except Exception as e:
                logger.error(f"Erro ao salvar registro: {record} - {str(e)}")
                continue

        # ------------------------------------------------------------------
        # 3) Persiste/atualiza objetos Venda consolidados por semana
        # ------------------------------------------------------------------
        for (year_number, week_number, plataforma_reg), totals in weekly_totals.items():
            venda_obj, created_flag = Venda.objects.get_or_create(
                empresa=empresa,
                ano=year_number,
                semana=str(week_number),
                plataforma=plataforma_reg,
                defaults={
                    'data': totals['data'],
                    'invest_realizado': totals['invest_realizado'],
                    'leads': totals['leads'],
                    'conversoes': totals['conversoes'],
                }
            )

            if not created_flag:
                # Mantém menor data (segunda-feira) registrada na semana
                if venda_obj.data > totals['data']:
                    venda_obj.data = totals['data']
                # Soma métricas
                venda_obj.invest_realizado += totals['invest_realizado']
                venda_obj.leads += totals['leads']
                venda_obj.conversoes += totals['conversoes']
            # Salva após alterações ou criação (save() já chamado em get_or_create se created)
            venda_obj.save()

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
