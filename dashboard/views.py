from venda.models import Venda
from datetime import datetime
import calendar
from django.db.models import Sum, Avg, Count, Q
from rest_framework import views
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from .serializers import DashboardSerializer, DashboardDataSerializer
import logging
from rest_framework import status

logger = logging.getLogger(__name__)

class DashboardAPIView(views.APIView):
    permission_classes = [AllowAny]

    def _calculate_weekly_average(self, weekly_data, field_name, week_numbers):
        """Calcula a média semanal somando os valores e dividindo pelo número de semanas reais"""
        if not weekly_data or not week_numbers:
            return [0] * len(week_numbers)
        
        # Cria um dicionário semana -> valor
        data_dict = {int(item['semana']): float(item[field_name] or 0) for item in weekly_data}
        valores = [data_dict.get(week, 0) for week in week_numbers]
        num_semanas = len([v for v in valores if v != 0]) or len(week_numbers)
        total = sum(valores)
        media = total / num_semanas if num_semanas > 0 else 0
        return [media] * len(week_numbers)

    def _fill_weekly_data(self, weekly_data, field_name, week_numbers):
        """Preenche os dados semanais conforme as semanas reais cadastradas"""
        if not weekly_data or not week_numbers:
            return [0] * len(week_numbers)
        data_dict = {int(item['semana']): float(item[field_name] or 0) for item in weekly_data}
        return [data_dict.get(week, 0) for week in week_numbers]

    def _fill_weekly_data_with_mean(self, weekly_data, field_name, week_numbers):
        """Preenche os dados semanais conforme as semanas reais cadastradas. Se não houver dado para uma semana, usa a média do mês anterior."""
        if not weekly_data or not week_numbers:
            return [0] * len(week_numbers)
        data_dict = {int(item['semana']): float(item[field_name] or 0) for item in weekly_data}
        valores_existentes = list(data_dict.values())
        media = sum(valores_existentes) / len(valores_existentes) if valores_existentes else 0
        return [data_dict.get(week, media) for week in week_numbers]

    def get_queryset(self):
        empresa = getattr(self.request, 'empresa', None)
        if not empresa:
            return Venda.objects.none()
        return Venda.objects.filter(empresa=empresa)

    def get(self, request):
        try:
            serializer = DashboardSerializer(data=request.query_params)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            year = serializer.validated_data['year']
            month = serializer.validated_data.get('month')
            comparison_type = serializer.validated_data.get('comparisonType', 'mes_anterior')
            filter_type = serializer.validated_data['filterType']

            empresa = getattr(self.request, 'empresa', None)
            queryset = self.get_queryset().filter(ano=year)
            
            # Só filtra por mês se não for filtro anual
            if month and filter_type != 'ano':
                queryset = queryset.filter(data__month=month)

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

            # OTIMIZAÇÃO: Uma única query para todas as métricas principais
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

            # OTIMIZAÇÃO: Uma única query para dados históricos
            if filter_type == 'ano':
                historical_data = queryset.order_by('data__month').values('data__month').annotate(
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
            else:
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

            # Calcula dados de comparação baseado no tipo selecionado
            if filter_type == 'mes' and month:
                comparison_metrics = {}
                comparison_queryset = None
                
                if comparison_type == 'mes_anterior':
                    # Compara com o mês anterior
                    prev_month = month - 1
                    prev_year = year
                    if prev_month == 0:
                        prev_month = 12
                        prev_year = year - 1
                    
                    comparison_queryset = self.get_queryset().filter(
                        ano=prev_year,
                        data__month=prev_month,
                        empresa=empresa,
                        **plataforma_filter
                    )
                    
                elif comparison_type == 'mes_aleatorio':
                    # Compara com um mês específico selecionado pelo usuário
                    comparison_month = request.query_params.get('comparisonMonth')
                    comparison_year = request.query_params.get('comparisonYear')
                    
                    # Se não foram fornecidos, usa valores padrão
                    if not comparison_month:
                        comparison_month = 6  # Junho como padrão
                    if not comparison_year:
                        comparison_year = year
                    
                    comparison_queryset = self.get_queryset().filter(
                        ano=int(comparison_year),
                        data__month=int(comparison_month),
                        empresa=empresa,
                        **plataforma_filter
                    )
                    
                elif comparison_type == 'media_ano':
                    # Calcula média do ano atual até o mês atual
                    comparison_queryset = self.get_queryset().filter(
                        ano=year,
                        data__month__lte=month,
                        empresa=empresa,
                        **plataforma_filter
                    )
                    
                elif comparison_type == 'ano_anterior':
                    # Compara com o mesmo mês do ano anterior
                    comparison_queryset = self.get_queryset().filter(
                        ano=year - 1,
                        data__month=month,
                        empresa=empresa,
                        **plataforma_filter
                    )
                    
                elif comparison_type == 'ano_especifico':
                    # Compara com o mesmo mês de um ano específico
                    comparison_year = request.query_params.get('comparisonYear')
                    if not comparison_year:
                        comparison_year = year - 1  # Fallback para ano anterior
                    else:
                        comparison_year = int(comparison_year)
                    
                    comparison_queryset = self.get_queryset().filter(
                        ano=comparison_year,
                        data__month=month,
                        empresa=empresa,
                        **plataforma_filter
                    )
                
                # Calcula métricas de comparação
                comparison_metrics = None
                if comparison_queryset and comparison_queryset.exists():
                    if comparison_type == 'media_ano':
                        # Para média do ano, calcula a média dos meses
                        comparison_data = comparison_queryset.values('data__month').annotate(
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
                        )
                        
                        num_months = len(comparison_data)
                        if num_months > 0:
                            comparison_metrics = {
                                'invest_realizado_avg': sum(item['invest_realizado_sum'] or 0 for item in comparison_data) / num_months,
                                'invest_projetado_avg': sum(item['invest_projetado_sum'] or 0 for item in comparison_data) / num_months,
                                'faturamento_avg': sum(item['faturamento_sum'] or 0 for item in comparison_data) / num_months,
                                'faturamento_campanha_avg': sum(item['faturamento_campanha_sum'] or 0 for item in comparison_data) / num_months,
                                'clientes_novos_avg': sum(item['clientes_novos_sum'] or 0 for item in comparison_data) / num_months,
                                'clientes_recorrentes_avg': sum(item['clientes_recorrentes_sum'] or 0 for item in comparison_data) / num_months,
                                'leads_avg': sum(item['leads_sum'] or 0 for item in comparison_data) / num_months,
                                'vendas_google_avg': sum(item['vendas_google_sum'] or 0 for item in comparison_data) / num_months,
                                'vendas_instagram_avg': sum(item['vendas_instagram_sum'] or 0 for item in comparison_data) / num_months,
                                'vendas_facebook_avg': sum(item['vendas_facebook_sum'] or 0 for item in comparison_data) / num_months,
                                'roi_avg': sum(item['roi_avg'] or 0 for item in comparison_data if item['roi_avg'] is not None) / len([x for x in comparison_data if x['roi_avg'] is not None]) if any(item['roi_avg'] is not None for item in comparison_data) else 0,
                                'ticket_medio_avg': sum(item['ticket_medio_avg'] or 0 for item in comparison_data if item['ticket_medio_avg'] is not None) / len([x for x in comparison_data if x['ticket_medio_avg'] is not None]) if any(item['ticket_medio_avg'] is not None for item in comparison_data) else 0,
                                'taxa_conversao_avg': sum(item['taxa_conversao_avg'] or 0 for item in comparison_data if item['taxa_conversao_avg'] is not None) / len([x for x in comparison_data if x['taxa_conversao_avg'] is not None]) if any(item['taxa_conversao_avg'] is not None for item in comparison_data) else 0,
                                'cac_avg': sum(item['cac_avg'] or 0 for item in comparison_data if item['cac_avg'] is not None) / len([x for x in comparison_data if x['cac_avg'] is not None]) if any(item['cac_avg'] is not None for item in comparison_data) else 0
                            }
                            
                            # Verifica se os dados calculados são válidos (pelo menos um valor maior que 0)
                            has_valid_data = any([
                                comparison_metrics.get('faturamento_avg', 0) or 0,
                                comparison_metrics.get('clientes_novos_avg', 0) or 0,
                                comparison_metrics.get('leads_avg', 0) or 0,
                                comparison_metrics.get('invest_realizado_avg', 0) or 0
                            ]) > 0
                            
                            if not has_valid_data:
                                comparison_metrics = None
                    else:
                        # Para comparação com mês específico, usa os valores diretos
                        comparison_metrics = comparison_queryset.aggregate(
                            invest_realizado_avg=Sum('invest_realizado'),
                            invest_projetado_avg=Sum('invest_projetado'),
                            faturamento_avg=Sum('fat_geral'),
                            faturamento_campanha_avg=Sum('fat_camp_realizado'),
                            clientes_novos_avg=Sum('clientes_novos'),
                            clientes_recorrentes_avg=Sum('clientes_recorrentes'),
                            leads_avg=Sum('leads'),
                            vendas_google_avg=Sum('vendas_google'),
                            vendas_instagram_avg=Sum('vendas_instagram'),
                            vendas_facebook_avg=Sum('vendas_facebook'),
                            roi_avg=Avg('roi_realizado'),
                            ticket_medio_avg=Avg('ticket_medio_realizado'),
                            taxa_conversao_avg=Avg('taxa_conversao'),
                            cac_avg=Avg('cac_realizado')
                        )
                        
                        # Verifica se os dados calculados são válidos (pelo menos um valor maior que 0)
                        has_valid_data = any([
                            comparison_metrics.get('faturamento_avg', 0) or 0,
                            comparison_metrics.get('clientes_novos_avg', 0) or 0,
                            comparison_metrics.get('leads_avg', 0) or 0,
                            comparison_metrics.get('invest_realizado_avg', 0) or 0
                        ]) > 0
                        
                        if not has_valid_data:
                            comparison_metrics = None
                
                # Se não há dados de comparação, retorna valores zerados para mostrar "Sem dados para comparação"
                if not comparison_metrics:
                    comparison_metrics = {
                        'invest_realizado_avg': 0,
                        'invest_projetado_avg': 0,
                        'faturamento_avg': 0,
                        'faturamento_campanha_avg': 0,
                        'clientes_novos_avg': 0,
                        'clientes_recorrentes_avg': 0,
                        'leads_avg': 0,
                        'vendas_google_avg': 0,
                        'vendas_instagram_avg': 0,
                        'vendas_facebook_avg': 0,
                        'roi_avg': 0,
                        'ticket_medio_avg': 0,
                        'taxa_conversao_avg': 0,
                        'cac_avg': 0
                    }
                
                yearly_metrics.update(comparison_metrics)
            
            elif filter_type == 'ano':
                # Para filtro anual, calcula médias baseadas no tipo de comparação
                # Determina o ano de comparação baseado no tipo
                comparison_year = year
                if comparison_type == 'ano_anterior':
                    comparison_year = year - 1
                elif comparison_type == 'ano_especifico':
                    # Pega o ano específico selecionado pelo usuário
                    comparison_year = request.query_params.get('comparisonYear')
                    if not comparison_year:
                        comparison_year = year - 1  # Fallback para ano anterior
                    else:
                        comparison_year = int(comparison_year)
                
                # Busca dados do ano de comparação
                comparison_year_data = Venda.objects.filter(
                    ano=comparison_year,
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

                num_months_comparison = len(comparison_year_data)
                
                if num_months_comparison > 0:
                    yearly_metrics.update({
                        'invest_realizado_avg': sum(item['invest_realizado_sum'] or 0 for item in comparison_year_data),
                        'invest_projetado_avg': sum(item['invest_projetado_sum'] or 0 for item in comparison_year_data),
                        'faturamento_avg': sum(item['faturamento_sum'] or 0 for item in comparison_year_data),
                        'faturamento_campanha_avg': sum(item['faturamento_campanha_sum'] or 0 for item in comparison_year_data),
                        'clientes_novos_avg': sum(item['clientes_novos_sum'] or 0 for item in comparison_year_data),
                        'clientes_recorrentes_avg': sum(item['clientes_recorrentes_sum'] or 0 for item in comparison_year_data),
                        'leads_avg': sum(item['leads_sum'] or 0 for item in comparison_year_data),
                        'vendas_google_avg': sum(item['vendas_google_sum'] or 0 for item in comparison_year_data),
                        'vendas_instagram_avg': sum(item['vendas_instagram_sum'] or 0 for item in comparison_year_data),
                        'vendas_facebook_avg': sum(item['vendas_facebook_sum'] or 0 for item in comparison_year_data),
                        # Para métricas que são médias (ROI, ticket médio, etc.), mantém a média dos valores existentes
                        'roi_avg': sum(item['roi_avg'] or 0 for item in comparison_year_data if item['roi_avg'] is not None) / len([x for x in comparison_year_data if x['roi_avg'] is not None]) if any(item['roi_avg'] is not None for item in comparison_year_data) else 0,
                        'ticket_medio_avg': sum(item['ticket_medio_avg'] or 0 for item in comparison_year_data if item['ticket_medio_avg'] is not None) / len([x for x in comparison_year_data if x['ticket_medio_avg'] is not None]) if any(item['ticket_medio_avg'] is not None for item in comparison_year_data) else 0,
                        'taxa_conversao_avg': sum(item['taxa_conversao_avg'] or 0 for item in comparison_year_data if item['taxa_conversao_avg'] is not None) / len([x for x in comparison_year_data if x['taxa_conversao_avg'] is not None]) if any(item['taxa_conversao_avg'] is not None for item in comparison_year_data) else 0,
                        'cac_avg': sum(item['cac_avg'] or 0 for item in comparison_year_data if item['cac_avg'] is not None) / len([x for x in comparison_year_data if x['cac_avg'] is not None]) if any(item['cac_avg'] is not None for item in comparison_year_data) else 0
                    })
                else:
                    # Se não há dados no ano de comparação, retorna valores zerados para mostrar "Sem dados para comparação"
                    yearly_metrics.update({
                        'invest_realizado_avg': 0,
                        'invest_projetado_avg': 0,
                        'faturamento_avg': 0,
                        'faturamento_campanha_avg': 0,
                        'clientes_novos_avg': 0,
                        'clientes_recorrentes_avg': 0,
                        'leads_avg': 0,
                        'vendas_google_avg': 0,
                        'vendas_instagram_avg': 0,
                        'vendas_facebook_avg': 0,
                        'roi_avg': 0,
                        'ticket_medio_avg': 0,
                        'taxa_conversao_avg': 0,
                        'cac_avg': 0
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

            # OTIMIZAÇÃO: Busca dados semanais apenas quando necessário
            weekly_data_current = []
            weekly_data_previous = []
            weekly_labels = []
            
            if filter_type == 'mes' and month:
                try:
                    # Dados semanais do mês atual
                    weekly_data_current = Venda.objects.filter(
                        ano=year,
                        data__month=month,
                        empresa=empresa,
                        **plataforma_filter
                    ).values('semana').annotate(
                        fat_camp_realizado_sum=Sum('fat_camp_realizado'),
                        fat_geral_sum=Sum('fat_geral')
                    ).order_by('semana')
                    
                    # Dados semanais do mês anterior para comparação
                    previous_month = month - 1
                    previous_year = year
                    if previous_month == 0:
                        previous_month = 12
                        previous_year = year - 1
                    
                    weekly_data_previous = Venda.objects.filter(
                        ano=previous_year,
                        data__month=previous_month,
                        empresa=empresa,
                        **plataforma_filter
                    ).values('semana').annotate(
                        fat_camp_realizado_sum=Sum('fat_camp_realizado'),
                        fat_geral_sum=Sum('fat_geral')
                    ).order_by('semana')
                    
                    # Descobre as semanas reais cadastradas (ex: [19, 20, 21])
                    week_numbers = [int(item['semana']) for item in weekly_data_current]
                    weekly_labels = [f"Semana {w}" for w in week_numbers]
                    
                except Exception as e:
                    logger.error(f"Erro ao buscar dados semanais: {str(e)}")
                    weekly_labels = []
                    week_numbers = []
            else:
                weekly_labels = []
                week_numbers = []

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
                'labels': [datetime(2000, item['data__month'], 1).strftime('%B').replace('January', 'Janeiro').replace('February', 'Fevereiro').replace('March', 'Março').replace('April', 'Abril').replace('May', 'Maio').replace('June', 'Junho').replace('July', 'Julho').replace('August', 'Agosto').replace('September', 'Setembro').replace('October', 'Outubro').replace('November', 'Novembro').replace('December', 'Dezembro') if filter_type == 'ano' else item['data'].strftime('%d/%m') for item in historical_data] if historical_data else [],
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
                'cac_data': [float(item['cac_data'] or 0) for item in historical_data],
                
                # Dados de média para os gráficos (mesmo valor para todos os meses)
                'roi_avg_data': [float(yearly_metrics.get('roi_avg', 0))] * len(historical_data) if historical_data else [],
                'ticket_medio_avg_data': [float(yearly_metrics.get('ticket_medio_avg', 0))] * len(historical_data) if historical_data else [],
                'taxa_conversao_avg_data': [float(yearly_metrics.get('taxa_conversao_avg', 0))] * len(historical_data) if historical_data else [],
                'cac_avg_data': [float(yearly_metrics.get('cac_avg', 0))] * len(historical_data) if historical_data else [],
                'faturamento_avg_data': [float(yearly_metrics.get('faturamento_avg', 0))] * len(historical_data) if historical_data else [],
                'clientes_novos_avg_data': [float(yearly_metrics.get('clientes_novos_avg', 0))] * len(historical_data) if historical_data else [],
                'leads_avg_data': [float(yearly_metrics.get('leads_avg', 0))] * len(historical_data) if historical_data else [],
                'invest_realizado_avg_data': [float(yearly_metrics.get('invest_realizado_avg', 0))] * len(historical_data) if historical_data else [],
                
                # Dados semanais para os novos gráficos
                'weekly_labels': weekly_labels,
                'weekly_fat_camp_current': self._fill_weekly_data(weekly_data_current, 'fat_camp_realizado_sum', week_numbers),
                'weekly_fat_camp_previous': self._fill_weekly_data_with_mean(weekly_data_previous, 'fat_camp_realizado_sum', week_numbers),
                'weekly_fat_geral_current': self._fill_weekly_data(weekly_data_current, 'fat_geral_sum', week_numbers),
                'weekly_fat_geral_previous': self._fill_weekly_data_with_mean(weekly_data_previous, 'fat_geral_sum', week_numbers),
                
                # Calcula médias semanais corretamente
                'weekly_fat_camp_avg': self._calculate_weekly_average(weekly_data_current, 'fat_camp_realizado_sum', week_numbers),
                'weekly_fat_geral_avg': self._calculate_weekly_average(weekly_data_current, 'fat_geral_sum', week_numbers)
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

            serializer = DashboardDataSerializer(response_data)
            return Response(serializer.data)

        except Exception as e:
            logger.error(f"Erro geral na view do dashboard: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AllYearsDashboardAPIView(views.APIView):
    permission_classes = [AllowAny]

    def get_queryset(self):
        empresa = getattr(self.request, 'empresa', None)
        if not empresa:
            return Venda.objects.none()
        return Venda.objects.filter(empresa=empresa)

    def get(self, request):
        try:
            logger.info(f"Recebendo requisição de todos os anos com params: {request.query_params}")
            
            plataforma = request.query_params.get('plataforma')
            if not plataforma:
                return Response(
                    {'error': 'Parâmetro plataforma é obrigatório'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            empresa = getattr(self.request, 'empresa', None)
            queryset = self.get_queryset()
            
            # Filtro de plataforma
            if plataforma == 'google':
                queryset = queryset.filter(vendas_google__gt=0)
            elif plataforma == 'instagram':
                queryset = queryset.filter(vendas_instagram__gt=0)
            elif plataforma == 'facebook':
                queryset = queryset.filter(vendas_facebook__gt=0)
            
            # Busca todos os anos disponíveis
            available_years = list(queryset.values_list('ano', flat=True).distinct().order_by('ano'))
            
            if not available_years:
                return Response({
                    'available_years': [],
                    'years_data': {}
                }, status=status.HTTP_200_OK)
            
            # Calcula métricas para cada ano
            years_data = {}
            
            for year in available_years:
                year_queryset = queryset.filter(ano=year)
                
                metrics = year_queryset.aggregate(
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
                
                # Garantir que os valores são números
                years_data[year] = {
                    'invest_realizado': float(metrics['invest_realizado'] or 0),
                    'invest_projetado': float(metrics['invest_projetado'] or 0),
                    'faturamento': float(metrics['faturamento'] or 0),
                    'clientes_novos': float(metrics['clientes_novos'] or 0),
                    'faturamento_campanha': float(metrics['faturamento_campanha'] or 0),
                    'leads': float(metrics['leads'] or 0),
                    'vendas_google': float(metrics['vendas_google'] or 0),
                    'vendas_instagram': float(metrics['vendas_instagram'] or 0),
                    'vendas_facebook': float(metrics['vendas_facebook'] or 0),
                    'roi': float(metrics['roi'] or 0),
                    'ticket_medio': float(metrics['ticket_medio'] or 0),
                    'clientes_recorrentes': float(metrics['clientes_recorrentes'] or 0),
                    'taxa_conversao': float(metrics['taxa_conversao'] or 0),
                    'cac': float(metrics['cac'] or 0)
                }
                
                logger.warning(f"[ALL YEARS DASHBOARD] Ano {year} - ROI: {years_data[year]['roi']}, Ticket: {years_data[year]['ticket_medio']}, Taxa: {years_data[year]['taxa_conversao']}, CAC: {years_data[year]['cac']}")
            
            data = {
                'available_years': available_years,
                'years_data': years_data
            }
            
            logger.info(f"Dados de todos os anos retornados: {len(available_years)} anos encontrados")
            return Response(data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Erro geral no dashboard de todos os anos: {str(e)}")
            return Response(
                {'error': 'Erro interno do servidor'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AvailableYearsAPIView(views.APIView):
    permission_classes = [AllowAny]

    def get_queryset(self):
        empresa = getattr(self.request, 'empresa', None)
        if not empresa:
            return Venda.objects.none()
        return Venda.objects.filter(empresa=empresa)

    def get(self, request):
        try:
            logger.info(f"Recebendo requisição de anos disponíveis com params: {request.query_params}")
            
            plataforma = request.query_params.get('plataforma')
            if not plataforma:
                return Response(
                    {'error': 'Parâmetro plataforma é obrigatório'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            empresa = getattr(self.request, 'empresa', None)
            queryset = self.get_queryset()
            
            # Filtro de plataforma
            if plataforma == 'google':
                queryset = queryset.filter(vendas_google__gt=0)
            elif plataforma == 'instagram':
                queryset = queryset.filter(vendas_instagram__gt=0)
            elif plataforma == 'facebook':
                queryset = queryset.filter(vendas_facebook__gt=0)
            
            # Busca todos os anos disponíveis
            available_years = list(queryset.values_list('ano', flat=True).distinct().order_by('ano'))
            
            logger.info(f"Anos disponíveis para {plataforma}: {available_years}")
            return Response({
                'available_years': available_years
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Erro ao buscar anos disponíveis: {str(e)}")
            return Response(
                {'error': 'Erro interno do servidor'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )