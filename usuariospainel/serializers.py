from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import UserCompanyLink
from django.utils import timezone
from perfilusuario.models import PerfilUsuario

User = get_user_model()

class UserCompanyLinkSerializer(serializers.ModelSerializer):
    """
    Serializer para o modelo UserCompanyLink
    """
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.CharField(source='user.person_profile.name', read_only=True)
    empresa_nome = serializers.CharField(source='empresa.nome_fantasia', read_only=True)
    user_avatar = serializers.SerializerMethodField()

    class Meta:
        model = UserCompanyLink
        fields = [
            'id', 'user', 'user_email', 'user_name', 'empresa', 'empresa_nome',
            'position', 'status', 'permissions', 'created_at', 'updated_at',
            'expires_at', 'user_avatar'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'expires_at']

    def get_user_avatar(self, obj):
        try:
            perfil = PerfilUsuario.objects.get(usuario=obj.user)
            if perfil.foto:
                request = self.context.get('request')
                if request:
                    return request.build_absolute_uri(perfil.foto.url)
                return perfil.foto.url
        except PerfilUsuario.DoesNotExist:
            pass
        return None

class CreateUserCompanyLinkSerializer(serializers.ModelSerializer):
    """
    Serializer para criação de vínculo entre usuário e empresa
    """
    email = serializers.EmailField(write_only=True)
    position = serializers.CharField(max_length=100)
    permissions = serializers.JSONField()

    # Define níveis de permissão granulares
    PERMISSION_LEVELS = ['view', 'edit', 'full']

    def validate_permissions(self, value):
        # Valida os níveis de permissão para módulos
        if not isinstance(value, dict):
            raise serializers.ValidationError('Permissões devem ser um objeto contendo modulos')
        modulos = value.get('modulos', {})
        if not isinstance(modulos, dict):
            raise serializers.ValidationError('Permissões de módulos devem ser um objeto')
        for lvl in modulos.values():
            if lvl not in self.PERMISSION_LEVELS:
                raise serializers.ValidationError(
                    f"Nivel de permissão inválido: {lvl}. Opções válidas: {', '.join(self.PERMISSION_LEVELS)}"
                )
        return value

    class Meta:
        model = UserCompanyLink
        fields = ['email', 'position', 'permissions']

    def validate_email(self, value):
        try:
            user = User.objects.get(email=value)
            if user.user_type != 'PF':
                raise serializers.ValidationError('O email deve pertencer a uma pessoa física')
            return value
        except User.DoesNotExist:
            raise serializers.ValidationError('Usuário não cadastrado na nossa base de dados.')

    def create(self, validated_data):
        email = validated_data.pop('email')
        user = User.objects.get(email=email)
        
        # Usando a empresa atual do usuário PJ
        empresa = self.context['request'].user.empresa_atual
        if not empresa:
            raise serializers.ValidationError('Empresa não encontrada')

        if UserCompanyLink.objects.filter(user=user, empresa=empresa).exists():
            raise serializers.ValidationError('Este usuário já está vinculado à empresa')

        # Inicializa as permissões com um dicionário vazio para módulos
        permissions = validated_data.get('permissions', {})
        if not isinstance(permissions, dict):
            permissions = {}
        if 'modulos' not in permissions:
            permissions['modulos'] = {}
        
        validated_data['permissions'] = permissions

        # Removendo empresa do validated_data se existir
        validated_data.pop('empresa', None)

        expires_at = timezone.now() + timezone.timedelta(hours=1)

        return UserCompanyLink.objects.create(
            user=user,
            empresa=empresa,
            status='pending',
            expires_at=expires_at,
            **validated_data
        )

class UpdateUserCompanyLinkSerializer(serializers.ModelSerializer):
    """
    Serializer para atualização de vínculo entre usuário e empresa
    """
    # Garante campo JSON e valida níveis
    permissions = serializers.JSONField()
    PERMISSION_LEVELS = ['view', 'edit', 'full']

    def validate_permissions(self, value):
        # Valida os níveis de permissão para módulos na atualização
        modulos = value.get('modulos', {})
        if not isinstance(modulos, dict):
            raise serializers.ValidationError('Permissões de módulos devem ser um objeto')
        for lvl in modulos.values():
            if lvl not in self.PERMISSION_LEVELS:
                raise serializers.ValidationError(
                    f"Nivel de permissão inválido: {lvl}. Opções válidas: {', '.join(self.PERMISSION_LEVELS)}"
                )
        return value

    class Meta:
        model = UserCompanyLink
        fields = ['status', 'permissions']
        read_only_fields = ['status']

    def validate(self, data):
        if self.instance.status == 'rejected':
            raise serializers.ValidationError('Não é possível atualizar um vínculo recusado')
        return data 