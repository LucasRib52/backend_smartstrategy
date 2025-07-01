from rest_framework import serializers
from .models import Venda
from decimal import Decimal

class VendaSerializer(serializers.ModelSerializer):
    plataforma = serializers.CharField(required=True)
    # Sobrescreve os campos problemáticos para aceitar strings vazias
    leads = serializers.IntegerField(required=False, allow_null=True)
    clientes_novos = serializers.IntegerField(required=False, allow_null=True)
    clientes_recorrentes = serializers.IntegerField(required=False, allow_null=True)
    conversoes = serializers.IntegerField(required=False, allow_null=True)
    
    def to_internal_value(self, data):
        """Converte dados antes da validação"""
        # Converte strings vazias para None
        for field in ['leads', 'clientes_novos', 'clientes_recorrentes', 'conversoes']:
            if field in data and data[field] == '':
                data[field] = None
        
        return super().to_internal_value(data)
    
    def validate(self, data):
        """Limpa e converte dados antes da validação"""
        # Garante que a data seja obrigatória
        if 'data' not in data or not data['data']:
            raise serializers.ValidationError("Data é obrigatória")
        
        # Limpa campos vazios e converte para valores padrão
        cleaned_data = {}
        for field, value in data.items():
            if value == '' or value is None:
                # Campos decimal
                if field in ['invest_realizado', 'invest_projetado', 'vendas_google', 
                           'vendas_instagram', 'vendas_facebook', 'fat_proj', 
                           'fat_camp_realizado', 'fat_geral', 'ticket_medio_realizado']:
                    cleaned_data[field] = Decimal('0.00')
                # Campos inteiros
                elif field in ['leads', 'clientes_novos', 'clientes_recorrentes', 'conversoes']:
                    cleaned_data[field] = 0
                else:
                    cleaned_data[field] = value
            else:
                cleaned_data[field] = value
        
        return cleaned_data
    
    class Meta:
        model = Venda
        fields = '__all__'
        read_only_fields = ('mes', 'ano', 'semana', 'saldo_invest', 'saldo_fat', 
                          'roi_realizado', 'roas_realizado', 'cac_realizado', 
                          'arpu_realizado', 'taxa_conversao', 'clima') 