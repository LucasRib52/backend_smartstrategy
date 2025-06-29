from rest_framework import serializers
from .models import ConviteUsuario
from django.contrib.auth import get_user_model

User = get_user_model()

class ConviteUsuarioSerializer(serializers.ModelSerializer):
    """
    Serializer para listar e criar convites
    """
    empresa_nome = serializers.CharField(source='empresa.nome_fantasia', read_only=True)
    empresa_razao_social = serializers.CharField(source='empresa.razao_social', read_only=True)
    convidado_nome = serializers.CharField(source='convidado.get_full_name', read_only=True)

    class Meta:
        model = ConviteUsuario
        fields = [
            'id',
            'email_convidado',
            'empresa',
            'empresa_nome',
            'empresa_razao_social',
            'convidado',
            'convidado_nome',
            'status',
            'data_envio',
            'data_resposta',
            'data_expiracao'
        ]
        read_only_fields = ['status', 'data_envio', 'data_resposta', 'data_expiracao']

    def validate_email_convidado(self, value):
        """
        Valida se o email pertence a um usuário PF
        """
        try:
            user = User.objects.get(email=value)
            if user.user_type != 'PF':
                raise serializers.ValidationError('O email deve pertencer a um usuário PF')
        except User.DoesNotExist:
            pass  # Permite convidar usuários que ainda não existem no sistema
        return value

    def validate(self, data):
        """
        Validações adicionais
        """
        request = self.context.get('request')
        if not request:
            raise serializers.ValidationError('Request não encontrado no contexto')

        # Verifica se o usuário que está enviando é PJ
        if request.user.user_type != 'PJ':
            raise serializers.ValidationError('Apenas usuários PJ podem enviar convites')

        # Verifica se já existe um convite pendente para este email
        if ConviteUsuario.objects.filter(
            email_convidado=data['email_convidado'],
            empresa=data['empresa'],
            status='pending'
        ).exists():
            raise serializers.ValidationError('Já existe um convite pendente para este email')

        return data

class AceitarConviteSerializer(serializers.Serializer):
    """
    Serializer para aceitar convites
    """
    def validate(self, data):
        request = self.context.get('request')
        if not request:
            raise serializers.ValidationError('Request não encontrado no contexto')

        if request.user.user_type != 'PF':
            raise serializers.ValidationError('Apenas usuários PF podem aceitar convites')

        return data

class RecusarConviteSerializer(serializers.Serializer):
    """
    Serializer para recusar convites
    """
    def validate(self, data):
        request = self.context.get('request')
        if not request:
            raise serializers.ValidationError('Request não encontrado no contexto')

        if request.user.user_type != 'PF':
            raise serializers.ValidationError('Apenas usuários PF podem recusar convites')

        return data 