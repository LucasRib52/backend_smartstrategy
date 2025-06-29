from django.http import HttpResponse
from datetime import datetime
from io import BytesIO
import csv
from openpyxl import Workbook
from django.db.models import Sum, Avg
from django.db.models.functions import TruncMonth, TruncWeek

from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from .models import Venda
from .serializers import VendaSerializer
from empresas.mixins import EmpresaFilterMixin

class VendaViewSet(EmpresaFilterMixin, viewsets.ModelViewSet):
    queryset = Venda.objects.all()
    serializer_class = VendaSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['data', 'mes', 'ano', 'semana', 'vendas_google', 'vendas_instagram', 'vendas_facebook']
    search_fields = ['mes', 'ano', 'semana']
    ordering_fields = ['data', 'fat_geral', 'invest_realizado']

    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        # Obtém os parâmetros da requisição
        year = request.query_params.get('year', datetime.now().year)
        month = request.query_params.get('month', datetime.now().month)
        week = request.query_params.get('week')
        filter_type = request.query_params.get('filterType', 'mes')
        plataforma = request.query_params.get('plataforma', 'instagram')

        # Filtra as vendas pelo ano
        queryset = self.filter_queryset(self.get_queryset()).filter(ano=year)

        # Aplica filtros adicionais baseado no tipo de filtro
        if filter_type == 'mes':
            queryset = queryset.filter(mes=month)
        elif filter_type == 'semana' and week:
            queryset = queryset.filter(semana=week)

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
            vendas_tiktok=Sum('vendas_tiktok'),
            roi=Avg('roi_realizado'),
            ticket_medio=Avg('ticket_medio_realizado'),
            clientes_recorrentes=Sum('clientes_recorrentes'),
            taxa_conversao=Avg('taxa_conversao'),
            cac=Avg('cac_realizado')
        )

        # Calcula as médias anuais
        yearly_metrics = self.filter_queryset(self.get_queryset()).filter(ano=year).aggregate(
            invest_realizado_avg=Avg('invest_realizado'),
            invest_projetado_avg=Avg('invest_projetado'),
            faturamento_avg=Avg('fat_geral'),
            clientes_novos_avg=Avg('clientes_novos'),
            faturamento_campanha_avg=Avg('fat_camp_realizado'),
            leads_avg=Avg('leads'),
            vendas_google_avg=Avg('vendas_google'),
            vendas_instagram_avg=Avg('vendas_instagram'),
            vendas_facebook_avg=Avg('vendas_facebook'),
            vendas_tiktok_avg=Avg('vendas_tiktok'),
            roi_avg=Avg('roi_realizado'),
            ticket_medio_avg=Avg('ticket_medio_realizado'),
            clientes_recorrentes_avg=Avg('clientes_recorrentes'),
            taxa_conversao_avg=Avg('taxa_conversao'),
            cac_avg=Avg('cac_realizado')
        )

        # Prepara os dados para os gráficos
        if filter_type == 'mes':
            # Dados mensais
            monthly_data = queryset.annotate(
                month=TruncMonth('data')
            ).values('month').annotate(
                invest_realizado=Sum('invest_realizado'),
                invest_projetado=Sum('invest_projetado'),
                fat_camp_realizado=Sum('fat_camp_realizado'),
                fat_geral=Sum('fat_geral'),
                leads=Sum('leads'),
                clientes_novos=Sum('clientes_novos'),
                clientes_recorrentes=Sum('clientes_recorrentes'),
                vendas_google=Sum('vendas_google'),
                vendas_instagram=Sum('vendas_instagram'),
                vendas_facebook=Sum('vendas_facebook'),
                vendas_tiktok=Sum('vendas_tiktok'),
                taxa_conversao=Avg('taxa_conversao'),
                roi=Avg('roi_realizado'),
                ticket_medio=Avg('ticket_medio_realizado'),
                cac=Avg('cac_realizado')
            ).order_by('month')

            labels = [data['month'].strftime('%B') for data in monthly_data]
            invest_realizado_data = [float(data['invest_realizado'] or 0) for data in monthly_data]
            invest_projetado_data = [float(data['invest_projetado'] or 0) for data in monthly_data]
            fat_camp_realizado_data = [float(data['fat_camp_realizado'] or 0) for data in monthly_data]
            fat_geral_data = [float(data['fat_geral'] or 0) for data in monthly_data]
            leads_data = [float(data['leads'] or 0) for data in monthly_data]
            clientes_novos_data = [float(data['clientes_novos'] or 0) for data in monthly_data]
            clientes_recorrentes_data = [float(data['clientes_recorrentes'] or 0) for data in monthly_data]
            vendas_google_data = [float(data['vendas_google'] or 0) for data in monthly_data]
            vendas_instagram_data = [float(data['vendas_instagram'] or 0) for data in monthly_data]
            vendas_facebook_data = [float(data['vendas_facebook'] or 0) for data in monthly_data]
            vendas_tiktok_data = [float(data['vendas_tiktok'] or 0) for data in monthly_data]
            taxa_conversao_data = [float(data['taxa_conversao'] or 0) for data in monthly_data]
            roi_data = [float(data['roi'] or 0) for data in monthly_data]
            ticket_medio_data = [float(data['ticket_medio'] or 0) for data in monthly_data]
            cac_data = [float(data['cac'] or 0) for data in monthly_data]

        else:
            # Dados semanais
            weekly_data = queryset.annotate(
                week=TruncWeek('data')
            ).values('week').annotate(
                invest_realizado=Sum('invest_realizado'),
                invest_projetado=Sum('invest_projetado'),
                fat_camp_realizado=Sum('fat_camp_realizado'),
                fat_geral=Sum('fat_geral'),
                leads=Sum('leads'),
                clientes_novos=Sum('clientes_novos'),
                clientes_recorrentes=Sum('clientes_recorrentes'),
                vendas_google=Sum('vendas_google'),
                vendas_instagram=Sum('vendas_instagram'),
                vendas_facebook=Sum('vendas_facebook'),
                vendas_tiktok=Sum('vendas_tiktok'),
                taxa_conversao=Avg('taxa_conversao'),
                roi=Avg('roi_realizado'),
                ticket_medio=Avg('ticket_medio_realizado'),
                cac=Avg('cac_realizado')
            ).order_by('week')

            labels = [f"Semana {data['week'].isocalendar()[1]}" for data in weekly_data]
            invest_realizado_data = [float(data['invest_realizado'] or 0) for data in weekly_data]
            invest_projetado_data = [float(data['invest_projetado'] or 0) for data in weekly_data]
            fat_camp_realizado_data = [float(data['fat_camp_realizado'] or 0) for data in weekly_data]
            fat_geral_data = [float(data['fat_geral'] or 0) for data in weekly_data]
            leads_data = [float(data['leads'] or 0) for data in weekly_data]
            clientes_novos_data = [float(data['clientes_novos'] or 0) for data in weekly_data]
            clientes_recorrentes_data = [float(data['clientes_recorrentes'] or 0) for data in weekly_data]
            vendas_google_data = [float(data['vendas_google'] or 0) for data in weekly_data]
            vendas_instagram_data = [float(data['vendas_instagram'] or 0) for data in weekly_data]
            vendas_facebook_data = [float(data['vendas_facebook'] or 0) for data in weekly_data]
            vendas_tiktok_data = [float(data['vendas_tiktok'] or 0) for data in weekly_data]
            taxa_conversao_data = [float(data['taxa_conversao'] or 0) for data in weekly_data]
            roi_data = [float(data['roi'] or 0) for data in weekly_data]
            ticket_medio_data = [float(data['ticket_medio'] or 0) for data in weekly_data]
            cac_data = [float(data['cac'] or 0) for data in weekly_data]

        # Combina todos os dados em uma única resposta
        response_data = {
            **metrics,
            **yearly_metrics,
            'labels': labels,
            'invest_realizado_data': invest_realizado_data,
            'invest_projetado_data': invest_projetado_data,
            'fat_camp_realizado_data': fat_camp_realizado_data,
            'fat_geral_data': fat_geral_data,
            'leads_data': leads_data,
            'clientes_novos_data': clientes_novos_data,
            'clientes_recorrentes_data': clientes_recorrentes_data,
            'vendas_google_data': vendas_google_data,
            'vendas_instagram_data': vendas_instagram_data,
            'vendas_facebook_data': vendas_facebook_data,
            'vendas_tiktok_data': vendas_tiktok_data,
            'taxa_conversao_data': taxa_conversao_data,
            'roi_data': roi_data,
            'ticket_medio_data': ticket_medio_data,
            'cac_data': cac_data
        }

        return Response(response_data)

    @action(detail=False, methods=['get'])
    def export_csv(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="vendas.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            "Data", "Mês", "Ano", "Semana",
            "Invest. Realizado", "Invest. Projetado", "Saldo Invest.",
            "Vendas Google", "Vendas Instagram", "Vendas Facebook", "Vendas TikTok", "FAT Projetado", "FAT Campanha", "FAT Geral", "Saldo FAT",
            "ROI", "ROAS", "CAC", "TKT Médio", "ARPU",
            "Leads", "Novos", "Recorrentes", "Conversões", "Taxa Conv.", "Clima"
        ])

        for venda in queryset:
            writer.writerow([
                venda.data.strftime("%d/%m/%Y") if venda.data else "",
                venda.mes,
                venda.ano,
                venda.semana,
                venda.invest_realizado,
                venda.invest_projetado,
                venda.saldo_invest,
                venda.vendas_google,
                venda.vendas_instagram,
                venda.vendas_facebook,
                venda.vendas_tiktok,
                venda.fat_proj,
                venda.fat_camp_realizado,
                venda.fat_geral,
                venda.saldo_fat,
                venda.roi_realizado,
                venda.roas_realizado,
                venda.cac_realizado,
                venda.ticket_medio_realizado,
                venda.arpu_realizado,
                venda.leads,
                venda.clientes_novos,
                venda.clientes_recorrentes,
                venda.conversoes,
                venda.taxa_conversao,
                venda.clima,
            ])

        return response

    @action(detail=False, methods=['get'])
    def export_excel(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        workbook = Workbook()
        sheet = workbook.active

        header = [
            "Data", "Mês", "Ano", "Semana",
            "Invest. Realizado", "Invest. Projetado", "Saldo Invest.",
            "Vendas Google", "Vendas Instagram", "Vendas Facebook", "Vendas TikTok", "FAT Projetado", "FAT Campanha", "FAT Geral", "Saldo FAT",
            "ROI", "ROAS", "CAC", "TKT Médio", "ARPU",
            "Leads", "Novos", "Recorrentes", "Conversões", "Taxa Conv.", "Clima"
        ]
        sheet.append(header)

        for venda in queryset:
            row = [
                venda.data.strftime("%d/%m/%Y") if venda.data else "",
                venda.mes,
                venda.ano,
                venda.semana,
                venda.invest_realizado,
                venda.invest_projetado,
                venda.saldo_invest,
                venda.vendas_google,
                venda.vendas_instagram,
                venda.vendas_facebook,
                venda.vendas_tiktok,
                venda.fat_proj,
                venda.fat_camp_realizado,
                venda.fat_geral,
                venda.saldo_fat,
                venda.roi_realizado,
                venda.roas_realizado,
                venda.cac_realizado,
                venda.ticket_medio_realizado,
                venda.arpu_realizado,
                venda.leads,
                venda.clientes_novos,
                venda.clientes_recorrentes,
                venda.conversoes,
                venda.taxa_conversao,
                venda.clima,
            ]
            sheet.append(row)

        output = BytesIO()
        workbook.save(output)
        output.seek(0)

        response = HttpResponse(
            output,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="vendas.xlsx"'
        return response
