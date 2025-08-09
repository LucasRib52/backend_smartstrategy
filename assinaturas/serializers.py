from rest_framework import serializers
from .models import Plano, Assinatura
from django.utils import timezone


class PlanoSerializer(serializers.ModelSerializer):
    permissoes = serializers.SerializerMethodField()
    
    class Meta:
        model = Plano
        fields = [
            'id', 'codigo', 'nome', 'preco', 'duracao_dias', 'ativo', 
            'trial_days', 'auto_renew', 'permissoes', 'vantagens', 
            'desvantagens', 'descricao',
            # Permissões de módulos disponíveis via API
            'acesso_financeiro', 'acesso_marketing', 'acesso_influencer', 'acesso_analytics'
        ]
    
    def get_permissoes(self, obj):
        try:
            return obj.get_permissoes()
        except Exception as e:
            print(f"Erro ao obter permissões: {str(e)}")
            return []


class AssinaturaSerializer(serializers.ModelSerializer):
    plano = PlanoSerializer(read_only=True)
    dias_restantes = serializers.SerializerMethodField()

    class Meta:
        model = Assinatura
        fields = [
            'id', 'plano', 'inicio', 'fim', 'ativa', 'expirada', 'dias_restantes',
            'asaas_subscription_id', 'asaas_customer_id', 'payment_status',
            'next_payment_date', 'trial_end_date'
        ]

    def get_dias_restantes(self, obj):
        try:
            # Se a assinatura está expirada, retorna 0 diretamente
            if obj.expirada:
                return 0

            # Calcula a diferença entre a data de vencimento e a data atual
            # Sem adicionar +1 para manter consistência com o Asaas
            dias_restantes = (obj.fim.date() - timezone.now().date()).days

            # Garante que nunca seja negativo
            return max(dias_restantes, 0)
        except Exception as e:
            print(f"Erro ao calcular dias restantes: {str(e)}")
            return 0 