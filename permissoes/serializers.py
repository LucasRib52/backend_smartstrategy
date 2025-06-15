from rest_framework import serializers
from .models import ModuloPermissao
from usuariospainel.models import UserCompanyLink

class ModuloPermissaoSerializer(serializers.ModelSerializer):
    """
    Serializer para o modelo ModuloPermissao
    """
    class Meta:
        model = ModuloPermissao
        fields = ['codigo', 'nome', 'descricao', 'ativo']
        read_only_fields = ['codigo']

class UserPermissaoSerializer(serializers.ModelSerializer):
    """
    Serializer para as permissões do usuário
    """
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    modulos = serializers.SerializerMethodField()

    class Meta:
        model = UserCompanyLink
        fields = ['id', 'user_name', 'user_email', 'position', 'status', 'modulos']
        read_only_fields = ['id', 'user_name', 'user_email', 'status']

    def get_modulos(self, obj):
        """
        Retorna as permissões dos módulos do usuário
        """
        return obj.permissions.get('modulos', {})

    def to_representation(self, instance):
        """
        Adiciona informações adicionais na representação
        """
        data = super().to_representation(instance)
        
        # Adiciona informações dos módulos
        modulos = ModuloPermissao.get_modulos_ativos()
        permissoes = data['modulos']
        
        modulos_data = []
        for modulo in modulos:
            modulos_data.append({
                'codigo': modulo.codigo,
                'nome': modulo.nome,
                'descricao': modulo.descricao,
                'tem_permissao': permissoes.get(modulo.codigo, False)
            })
        
        data['modulos'] = modulos_data
        return data 