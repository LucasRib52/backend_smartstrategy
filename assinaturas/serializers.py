from rest_framework import serializers
from .models import Plano, Assinatura
from django.utils import timezone


class PlanoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plano
        fields = ['id', 'codigo', 'nome', 'preco', 'duracao_dias']


class AssinaturaSerializer(serializers.ModelSerializer):
    plano = PlanoSerializer(read_only=True)
    dias_restantes = serializers.SerializerMethodField()

    class Meta:
        model = Assinatura
        fields = ['id', 'plano', 'inicio', 'fim', 'ativa', 'expirada', 'dias_restantes']

    def get_dias_restantes(self, obj):
        # Se assinatura expirou, já retorna 0
        if obj.expirada:
            return 0

        # Dias transcorridos desde o início
        elapsed_days = (timezone.now().date() - obj.inicio.date()).days

        # Calcula restantes em função da duração atual do plano (atualizada em tempo real)
        dias_restantes = obj.plano.duracao_dias - elapsed_days

        return max(dias_restantes, 0) 