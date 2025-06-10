from rest_framework import serializers
from empresas.models import Empresa

class EmpresaSelecionarPerfilSerializer(serializers.ModelSerializer):
    logomarca_url = serializers.SerializerMethodField()

    class Meta:
        model = Empresa
        fields = ['id', 'nome_fantasia', 'cnpj', 'email_comercial', 'logomarca_url']

    def get_logomarca_url(self, obj):
        request = self.context.get('request')
        if hasattr(obj, 'logomarca') and obj.logomarca and obj.logomarca.imagem:
            url = obj.logomarca.imagem.url
            if request is not None:
                return request.build_absolute_uri(url)
            return url
        return None

class EmpresaSerializer(serializers.ModelSerializer):
    logomarca_url = serializers.SerializerMethodField()

    class Meta:
        model = Empresa
        fields = ['id', 'nome_fantasia', 'email_comercial', 'cnpj', 'logomarca_url']

    def get_logomarca_url(self, obj):
        request = self.context.get('request')
        if hasattr(obj, 'logomarca') and obj.logomarca and obj.logomarca.imagem:
            url = obj.logomarca.imagem.url
            if request is not None:
                return request.build_absolute_uri(url)
            return url
        return None 