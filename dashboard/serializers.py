from rest_framework import serializers
from venda.models import Venda

class DashboardSerializer(serializers.Serializer):
    year = serializers.IntegerField(required=True)
    month = serializers.IntegerField(required=False, allow_null=True)
    week = serializers.IntegerField(required=False, allow_null=True)
    filterType = serializers.ChoiceField(choices=['ano', 'mes', 'semana'], required=True)

    def validate(self, data):
        if data['filterType'] == 'mes' and not data.get('month'):
            raise serializers.ValidationError("O mês é obrigatório quando o filtro é mensal")
        if data['filterType'] == 'semana':
            if not data.get('week'):
                raise serializers.ValidationError("A semana é obrigatória quando o filtro é semanal")
            if not data.get('month'):
                raise serializers.ValidationError("O mês é obrigatório quando o filtro é semanal")
            # Valida se o número da semana está dentro do intervalo possível (1-53)
            if data['week'] < 1 or data['week'] > 53:
                raise serializers.ValidationError("Número da semana inválido")
        # Para filtro anual, o mês não é obrigatório
        return data

class DashboardDataSerializer(serializers.Serializer):
    # Dados para os cards
    invest_realizado = serializers.FloatField()
    invest_projetado = serializers.FloatField()
    faturamento = serializers.FloatField()
    clientes_novos = serializers.IntegerField()
    faturamento_campanha = serializers.FloatField()
    leads = serializers.IntegerField()
    vendas_google = serializers.FloatField()
    vendas_instagram = serializers.FloatField()
    vendas_facebook = serializers.FloatField()
    roi = serializers.FloatField()
    ticket_medio = serializers.FloatField()
    clientes_recorrentes = serializers.IntegerField()
    taxa_conversao = serializers.FloatField()
    cac = serializers.FloatField()

    # Campos de média
    invest_realizado_avg = serializers.FloatField(required=False, default=0)
    invest_projetado_avg = serializers.FloatField(required=False, default=0)
    faturamento_avg = serializers.FloatField(required=False, default=0)
    faturamento_campanha_avg = serializers.FloatField(required=False, default=0)
    clientes_novos_avg = serializers.FloatField(required=False, default=0)
    clientes_recorrentes_avg = serializers.FloatField(required=False, default=0)
    leads_avg = serializers.FloatField(required=False, default=0)
    vendas_google_avg = serializers.FloatField(required=False, default=0)
    vendas_instagram_avg = serializers.FloatField(required=False, default=0)
    vendas_facebook_avg = serializers.FloatField(required=False, default=0)
    roi_avg = serializers.FloatField(required=False, default=0)
    ticket_medio_avg = serializers.FloatField(required=False, default=0)
    taxa_conversao_avg = serializers.FloatField(required=False, default=0)
    cac_avg = serializers.FloatField(required=False, default=0)

    # Dados para os gráficos
    labels = serializers.ListField(child=serializers.CharField())
    invest_realizado_data = serializers.ListField(child=serializers.FloatField())
    invest_projetado_data = serializers.ListField(child=serializers.FloatField())
    saldo_invest_data = serializers.ListField(child=serializers.FloatField())
    fat_camp_realizado_data = serializers.ListField(child=serializers.FloatField())
    fat_geral_data = serializers.ListField(child=serializers.FloatField())
    saldo_fat_data = serializers.ListField(child=serializers.FloatField())
    leads_data = serializers.ListField(child=serializers.IntegerField())
    clientes_novos_data = serializers.ListField(child=serializers.IntegerField())
    clientes_recorrentes_data = serializers.ListField(child=serializers.IntegerField())
    vendas_google_data = serializers.ListField(child=serializers.FloatField())
    vendas_instagram_data = serializers.ListField(child=serializers.FloatField())
    vendas_facebook_data = serializers.ListField(child=serializers.FloatField())
    taxa_conversao_data = serializers.ListField(child=serializers.FloatField())
    roi_data = serializers.ListField(child=serializers.FloatField())
    ticket_medio_data = serializers.ListField(child=serializers.FloatField())
    cac_data = serializers.ListField(child=serializers.FloatField())
    
    # Dados de média para gráficos
    roi_avg_data = serializers.ListField(child=serializers.FloatField(), required=False, default=[])
    ticket_medio_avg_data = serializers.ListField(child=serializers.FloatField(), required=False, default=[])
    taxa_conversao_avg_data = serializers.ListField(child=serializers.FloatField(), required=False, default=[])
    cac_avg_data = serializers.ListField(child=serializers.FloatField(), required=False, default=[])
    faturamento_avg_data = serializers.ListField(child=serializers.FloatField(), required=False, default=[])
    clientes_novos_avg_data = serializers.ListField(child=serializers.FloatField(), required=False, default=[])
    leads_avg_data = serializers.ListField(child=serializers.FloatField(), required=False, default=[])
    invest_realizado_avg_data = serializers.ListField(child=serializers.FloatField(), required=False, default=[]) 