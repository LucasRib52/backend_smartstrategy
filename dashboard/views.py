from venda.models import Venda
from datetime import datetime
import calendar
from django.db.models import Sum, Avg, Count
from rest_framework import views
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from .serializers import DashboardSerializer, DashboardDataSerializer
import logging
from rest_framework import status

logger = logging.getLogger(__name__)

class DashboardAPIView(views.APIView):
    permission_classes = [AllowAny]

    def get_queryset(self):
        empresa = getattr(self.request, 'empresa', None)
        logger.warning(f"[DASHBOARD] Filtro empresa: {empresa} (ID: {getattr(empresa, 'id', None)}) para usuário {self.request.user.email}")
        if not empresa:
            return Venda.objects.none()
        return Venda.objects.filter(empresa=empresa)

    def get(self, request):
        try:
            logger.info(f"Recebendo requisição com params: {request.query_params}")
            
            serializer = DashboardSerializer(data=request.query_params)
            if not serializer.is_valid():
                logger.error(f"Erro de validação: {serializer.errors}")
                logger.error(f"Parâmetros recebidos: {request.query_params}")
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            year = serializer.validated_data['year']
            month = serializer.validated_data.get('month')
            week = serializer.validated_data.get('week')
            filter_type = serializer.validated_data['filterType']

            logger.info(f"Dashboard request - Year: {year}, Month: {month}, Week: {week}, Filter: {filter_type}")

            empresa = getattr(self.request, 'empresa', None)
            queryset = self.get_queryset().filter(ano=year)
            if month:
                queryset = queryset.filter(data__month=month)
            if week and filter_type == 'semana':
                queryset = queryset.filter(semana=week)

            plataforma = request.query_params.get('plataforma')
            if plataforma == 'google':
                queryset = queryset.filter(vendas_google__gt=0)
            elif plataforma == 'instagram':
                queryset = queryset.filter(vendas_instagram__gt=0)
            elif plataforma == 'facebook':
                queryset = queryset.filter(vendas_facebook__gt=0)

            # Filtro de plataforma para médias históricas
            plataforma_filter = {}
            if plataforma == 'google':
                plataforma_filter = {'vendas_google__gt': 0}
            elif plataforma == 'instagram':
                plataforma_filter = {'vendas_instagram__gt': 0}
            elif plataforma == 'facebook':
                plataforma_filter = {'vendas_facebook__gt': 0}

            # Calcula as métricas principais
            metrics = queryset.aggregate(
                invest_realizado=Sum('invest_realizado'),
                invest_projetado=Sum('invest_projetado'),
                faturamento=Sum('fat_geral'),
                clientes_novos=Sum('clientes_novos'),
                faturamento_campanha=Sum('fat_camp_realizado'),
                leads=Sum('leads'),
                vendas_google=Sum('vendas_google'),
                vendas_instagram=Sum('vendas_instagram'),
                vendas_facebook=Sum('vendas_facebook'),
                roi=Avg('roi_realizado'),
                ticket_medio=Avg('ticket_medio_realizado'),
                clientes_recorrentes=Sum('clientes_recorrentes'),
                taxa_conversao=Avg('taxa_conversao'),
                cac=Avg('cac_realizado')
            )

            # Inicializa o dicionário de médias anuais
            yearly_metrics = {}

            # Log detalhado dos valores para debug
            logger.warning(f"[DASHBOARD ROI] Valores para {plataforma}:")
            logger.warning(f"Investimento realizado: {metrics['invest_realizado']}")
            logger.warning(f"Faturamento geral: {metrics['faturamento']}")
            logger.warning(f"Faturamento campanha: {metrics['faturamento_campanha']}")
            logger.warning(f"ROI calculado: {metrics['roi']}")
            logger.warning(f"Vendas {plataforma}: {metrics[f'vendas_{plataforma}']}")

            # Log dos dados brutos para verificar os valores individuais
            for venda in queryset:
                logger.warning(f"[DASHBOARD ROI] Venda individual - Data: {venda.data}")
                logger.warning(f"Investimento: {venda.invest_realizado}")
                logger.warning(f"Fat Camp: {venda.fat_camp_realizado}")
                logger.warning(f"Fat Geral: {venda.fat_geral}")
                logger.warning(f"ROI: {venda.roi_realizado}")
                logger.warning(f"Vendas {plataforma}: {getattr(venda, f'vendas_{plataforma}')}")

            historical_data = queryset.order_by('data').values('data').annotate(
                invest_realizado_data=Sum('invest_realizado'),
                invest_projetado_data=Sum('invest_projetado'),
                fat_camp_realizado_data=Sum('fat_camp_realizado'),
                fat_geral_data=Sum('fat_geral'),
                leads_data=Sum('leads'),
                clientes_novos_data=Sum('clientes_novos'),
                clientes_recorrentes_data=Sum('clientes_recorrentes'),
                vendas_google_data=Sum('vendas_google'),
                vendas_instagram_data=Sum('vendas_instagram'),
                vendas_facebook_data=Sum('vendas_facebook'),
                taxa_conversao_data=Avg('taxa_conversao'),
                roi_data=Avg('roi_realizado'),
                ticket_medio_data=Avg('ticket_medio_realizado'),
                cac_data=Avg('cac_realizado')
            )

            if filter_type == 'mes' and month:
                previous_months_data = Venda.objects.filter(
                    ano=year,
                    data__month__lte=month,
                    empresa=empresa,
                    **plataforma_filter
                ).values('data__month').annotate(
                    invest_realizado_sum=Sum('invest_realizado'),
                    invest_projetado_sum=Sum('invest_projetado'),
                    faturamento_sum=Sum('fat_geral'),
                    faturamento_campanha_sum=Sum('fat_camp_realizado'),
                    clientes_novos_sum=Sum('clientes_novos'),
                    clientes_recorrentes_sum=Sum('clientes_recorrentes'),
                    leads_sum=Sum('leads'),
                    vendas_google_sum=Sum('vendas_google'),
                    vendas_instagram_sum=Sum('vendas_instagram'),
                    vendas_facebook_sum=Sum('vendas_facebook'),
                    roi_avg=Avg('roi_realizado'),
                    ticket_medio_avg=Avg('ticket_medio_realizado'),
                    taxa_conversao_avg=Avg('taxa_conversao'),
                    cac_avg=Avg('cac_realizado')
                ).exclude(
                    invest_realizado_sum__isnull=True,
                    faturamento_sum__isnull=True,
                    clientes_novos_sum__isnull=True
                ).order_by('data__month')

                num_months = len(previous_months_data)
                if num_months > 0:
                    yearly_metrics.update({
                        'invest_realizado_avg': sum(item['invest_realizado_sum'] or 0 for item in previous_months_data) / num_months,
                        'invest_projetado_avg': sum(item['invest_projetado_sum'] or 0 for item in previous_months_data) / num_months,
                        'faturamento_avg': sum(item['faturamento_sum'] or 0 for item in previous_months_data) / num_months,
                        'faturamento_campanha_avg': sum(item['faturamento_campanha_sum'] or 0 for item in previous_months_data) / num_months,
                        'clientes_novos_avg': sum(item['clientes_novos_sum'] or 0 for item in previous_months_data) / num_months,
                        'clientes_recorrentes_avg': sum(item['clientes_recorrentes_sum'] or 0 for item in previous_months_data) / num_months,
                        'leads_avg': sum(item['leads_sum'] or 0 for item in previous_months_data) / num_months,
                        'vendas_google_avg': sum(item['vendas_google_sum'] or 0 for item in previous_months_data) / num_months,
                        'vendas_instagram_avg': sum(item['vendas_instagram_sum'] or 0 for item in previous_months_data) / num_months,
                        'vendas_facebook_avg': sum(item['vendas_facebook_sum'] or 0 for item in previous_months_data) / num_months,
                        'roi_avg': sum(item['roi_avg'] or 0 for item in previous_months_data if item['roi_avg'] is not None) / len([x for x in previous_months_data if x['roi_avg'] is not None]) if any(item['roi_avg'] is not None for item in previous_months_data) else 0,
                        'ticket_medio_avg': sum(item['ticket_medio_avg'] or 0 for item in previous_months_data if item['ticket_medio_avg'] is not None) / len([x for x in previous_months_data if x['ticket_medio_avg'] is not None]) if any(item['ticket_medio_avg'] is not None for item in previous_months_data) else 0,
                        'taxa_conversao_avg': sum(item['taxa_conversao_avg'] or 0 for item in previous_months_data if item['taxa_conversao_avg'] is not None) / len([x for x in previous_months_data if x['taxa_conversao_avg'] is not None]) if any(item['taxa_conversao_avg'] is not None for item in previous_months_data) else 0,
                        'cac_avg': sum(item['cac_avg'] or 0 for item in previous_months_data if item['cac_avg'] is not None) / len([x for x in previous_months_data if x['cac_avg'] is not None]) if any(item['cac_avg'] is not None for item in previous_months_data) else 0
                    })
                else:
                    yearly_metrics.update({
                        'invest_realizado_avg': metrics['invest_realizado'] or 0,
                        'invest_projetado_avg': metrics['invest_projetado'] or 0,
                        'faturamento_avg': metrics['faturamento'] or 0,
                        'faturamento_campanha_avg': metrics['faturamento_campanha'] or 0,
                        'clientes_novos_avg': metrics['clientes_novos'] or 0,
                        'clientes_recorrentes_avg': metrics['clientes_recorrentes'] or 0,
                        'leads_avg': metrics['leads'] or 0,
                        'vendas_google_avg': metrics['vendas_google'] or 0,
                        'vendas_instagram_avg': metrics['vendas_instagram'] or 0,
                        'vendas_facebook_avg': metrics['vendas_facebook'] or 0,
                        'roi_avg': metrics['roi'] or 0,
                        'ticket_medio_avg': metrics['ticket_medio'] or 0,
                        'taxa_conversao_avg': metrics['taxa_conversao'] or 0,
                        'cac_avg': metrics['cac'] or 0
                    })
            
            elif filter_type == 'semana' and month and week:
                try:
                    all_weeks_data = Venda.objects.filter(
                        ano=year,
                        data__month__lte=month,
                        empresa=empresa,
                        **plataforma_filter
                    ).values('semana').annotate(
                        invest_realizado_sum=Sum('invest_realizado'),
                        invest_projetado_sum=Sum('invest_projetado'),
                        faturamento_sum=Sum('fat_geral'),
                        faturamento_campanha_sum=Sum('fat_camp_realizado'),
                        clientes_novos_sum=Sum('clientes_novos'),
                        clientes_recorrentes_sum=Sum('clientes_recorrentes'),
                        leads_sum=Sum('leads'),
                        vendas_google_sum=Sum('vendas_google'),
                        vendas_instagram_sum=Sum('vendas_instagram'),
                        vendas_facebook_sum=Sum('vendas_facebook'),
                        roi_avg=Avg('roi_realizado'),
                        ticket_medio_avg=Avg('ticket_medio_realizado'),
                        taxa_conversao_avg=Avg('taxa_conversao'),
                        cac_avg=Avg('cac_realizado')
                    ).exclude(
                        invest_realizado_sum__isnull=True,
                        faturamento_sum__isnull=True,
                        clientes_novos_sum__isnull=True
                    ).order_by('semana')

                    num_weeks = len(all_weeks_data)
                    if num_weeks > 0:
                        def safe_avg(items, key):
                            valid_items = [item[key] for item in items if item[key] is not None]
                            return sum(valid_items) / len(valid_items) if valid_items else 0

                        yearly_metrics.update({
                            'invest_realizado_avg': safe_avg(all_weeks_data, 'invest_realizado_sum'),
                            'invest_projetado_avg': safe_avg(all_weeks_data, 'invest_projetado_sum'),
                            'faturamento_avg': safe_avg(all_weeks_data, 'faturamento_sum'),
                            'faturamento_campanha_avg': safe_avg(all_weeks_data, 'faturamento_campanha_sum'),
                            'clientes_novos_avg': safe_avg(all_weeks_data, 'clientes_novos_sum'),
                            'clientes_recorrentes_avg': safe_avg(all_weeks_data, 'clientes_recorrentes_sum'),
                            'leads_avg': safe_avg(all_weeks_data, 'leads_sum'),
                            'vendas_google_avg': safe_avg(all_weeks_data, 'vendas_google_sum'),
                            'vendas_instagram_avg': safe_avg(all_weeks_data, 'vendas_instagram_sum'),
                            'vendas_facebook_avg': safe_avg(all_weeks_data, 'vendas_facebook_sum'),
                            'roi_avg': safe_avg(all_weeks_data, 'roi_avg'),
                            'ticket_medio_avg': safe_avg(all_weeks_data, 'ticket_medio_avg'),
                            'taxa_conversao_avg': safe_avg(all_weeks_data, 'taxa_conversao_avg'),
                            'cac_avg': safe_avg(all_weeks_data, 'cac_avg')
                        })

                        logger.info(f"Médias calculadas para {num_weeks} semanas históricas:")
                        logger.info(f"Faturamento avg: {yearly_metrics['faturamento_avg']}")
                        logger.info(f"Clientes novos avg: {yearly_metrics['clientes_novos_avg']}")
                        logger.info(f"ROI avg: {yearly_metrics['roi_avg']}")
                    else:
                        yearly_metrics.update({
                            'invest_realizado_avg': metrics['invest_realizado'] or 0,
                            'invest_projetado_avg': metrics['invest_projetado'] or 0,
                            'faturamento_avg': metrics['faturamento'] or 0,
                            'faturamento_campanha_avg': metrics['faturamento_campanha'] or 0,
                            'clientes_novos_avg': metrics['clientes_novos'] or 0,
                            'clientes_recorrentes_avg': metrics['clientes_recorrentes'] or 0,
                            'leads_avg': metrics['leads'] or 0,
                            'vendas_google_avg': metrics['vendas_google'] or 0,
                            'vendas_instagram_avg': metrics['vendas_instagram'] or 0,
                            'vendas_facebook_avg': metrics['vendas_facebook'] or 0,
                            'roi_avg': metrics['roi'] or 0,
                            'ticket_medio_avg': metrics['ticket_medio'] or 0,
                            'taxa_conversao_avg': metrics['taxa_conversao'] or 0,
                            'cac_avg': metrics['cac'] or 0
                        })
                except Exception as e:
                    logger.error(f"Erro ao calcular médias semanais: {str(e)}")
                    yearly_metrics.update({
                        'invest_realizado_avg': metrics['invest_realizado'] or 0,
                        'invest_projetado_avg': metrics['invest_projetado'] or 0,
                        'faturamento_avg': metrics['faturamento'] or 0,
                        'faturamento_campanha_avg': metrics['faturamento_campanha'] or 0,
                        'clientes_novos_avg': metrics['clientes_novos'] or 0,
                        'clientes_recorrentes_avg': metrics['clientes_recorrentes'] or 0,
                        'leads_avg': metrics['leads'] or 0,
                        'vendas_google_avg': metrics['vendas_google'] or 0,
                        'vendas_instagram_avg': metrics['vendas_instagram'] or 0,
                        'vendas_facebook_avg': metrics['vendas_facebook'] or 0,
                        'roi_avg': metrics['roi'] or 0,
                        'ticket_medio_avg': metrics['ticket_medio'] or 0,
                        'taxa_conversao_avg': metrics['taxa_conversao'] or 0,
                        'cac_avg': metrics['cac'] or 0
                    })

            # Combina todos os dados em uma única resposta
            response_data = {
                'invest_realizado': float(metrics['invest_realizado'] or 0),
                'invest_projetado': float(metrics['invest_projetado'] or 0),
                'faturamento': float(metrics['faturamento'] or 0),
                'faturamento_campanha': float(metrics['faturamento_campanha'] or 0),
                'clientes_novos': int(metrics['clientes_novos'] or 0),
                'clientes_recorrentes': int(metrics['clientes_recorrentes'] or 0),
                'leads': int(metrics['leads'] or 0),
                'vendas_google': float(metrics['vendas_google'] or 0),
                'vendas_instagram': float(metrics['vendas_instagram'] or 0),
                'vendas_facebook': float(metrics['vendas_facebook'] or 0),
                'roi': float(metrics['roi'] or 0),
                'ticket_medio': float(metrics['ticket_medio'] or 0),
                'taxa_conversao': float(metrics['taxa_conversao'] or 0),
                'cac': float(metrics['cac'] or 0),
                'labels': [item['data'].strftime('%d/%m') for item in historical_data],
                'invest_realizado_data': [float(item['invest_realizado_data'] or 0) for item in historical_data],
                'invest_projetado_data': [float(item['invest_projetado_data'] or 0) for item in historical_data],
                'saldo_invest_data': [float((item['invest_projetado_data'] or 0) - (item['invest_realizado_data'] or 0)) for item in historical_data],
                'fat_camp_realizado_data': [float(item['fat_camp_realizado_data'] or 0) for item in historical_data],
                'fat_geral_data': [float(item['fat_geral_data'] or 0) for item in historical_data],
                'saldo_fat_data': [float((item['fat_geral_data'] or 0) - (item['fat_camp_realizado_data'] or 0)) for item in historical_data],
                'leads_data': [int(item['leads_data'] or 0) for item in historical_data],
                'clientes_novos_data': [int(item['clientes_novos_data'] or 0) for item in historical_data],
                'clientes_recorrentes_data': [int(item['clientes_recorrentes_data'] or 0) for item in historical_data],
                'vendas_google_data': [float(item['vendas_google_data'] or 0) for item in historical_data],
                'vendas_instagram_data': [float(item['vendas_instagram_data'] or 0) for item in historical_data],
                'vendas_facebook_data': [float(item['vendas_facebook_data'] or 0) for item in historical_data],
                'taxa_conversao_data': [float(item['taxa_conversao_data'] or 0) for item in historical_data],
                'roi_data': [float(item['roi_data'] or 0) for item in historical_data],
                'ticket_medio_data': [float(item['ticket_medio_data'] or 0) for item in historical_data],
                'cac_data': [float(item['cac_data'] or 0) for item in historical_data]
            }

            # Adiciona as médias anuais se existirem
            if yearly_metrics:
                response_data.update({
                    'invest_realizado_avg': float(yearly_metrics.get('invest_realizado_avg', 0)),
                    'invest_projetado_avg': float(yearly_metrics.get('invest_projetado_avg', 0)),
                    'faturamento_avg': float(yearly_metrics.get('faturamento_avg', 0)),
                    'faturamento_campanha_avg': float(yearly_metrics.get('faturamento_campanha_avg', 0)),
                    'clientes_novos_avg': float(yearly_metrics.get('clientes_novos_avg', 0)),
                    'clientes_recorrentes_avg': float(yearly_metrics.get('clientes_recorrentes_avg', 0)),
                    'leads_avg': float(yearly_metrics.get('leads_avg', 0)),
                    'vendas_google_avg': float(yearly_metrics.get('vendas_google_avg', 0)),
                    'vendas_instagram_avg': float(yearly_metrics.get('vendas_instagram_avg', 0)),
                    'vendas_facebook_avg': float(yearly_metrics.get('vendas_facebook_avg', 0)),
                    'roi_avg': float(yearly_metrics.get('roi_avg', 0)),
                    'ticket_medio_avg': float(yearly_metrics.get('ticket_medio_avg', 0)),
                    'taxa_conversao_avg': float(yearly_metrics.get('taxa_conversao_avg', 0)),
                    'cac_avg': float(yearly_metrics.get('cac_avg', 0))
                })

            logger.info(f"Dados sendo enviados: {response_data}")
            logger.info(f"Médias calculadas: {yearly_metrics.get('invest_realizado_avg', 0)}, {yearly_metrics.get('faturamento_avg', 0)}, {yearly_metrics.get('clientes_novos_avg', 0)}")

            serializer = DashboardDataSerializer(response_data)
            return Response(serializer.data)

        except Exception as e:
            logger.error(f"Erro geral na view do dashboard: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)