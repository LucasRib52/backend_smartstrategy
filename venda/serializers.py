from rest_framework import serializers
from .models import Venda

class VendaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Venda
        fields = '__all__'
        read_only_fields = ('mes', 'ano', 'semana', 'saldo_invest', 'saldo_fat', 
                          'roi_realizado', 'roas_realizado', 'cac_realizado', 
                          'arpu_realizado', 'taxa_conversao', 'clima') 