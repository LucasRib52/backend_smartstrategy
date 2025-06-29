from rest_framework import serializers
from empresas.models import Empresa
from assinaturas.serializers import AssinaturaSerializer
from assinaturas.models import Assinatura
from .models import NotificacaoAdmin


class EmpresaAdminSerializer(serializers.ModelSerializer):
    assinatura_ativa = serializers.SerializerMethodField()
    plano_nome = serializers.SerializerMethodField()
    situacao = serializers.SerializerMethodField()

    class Meta:
        model = Empresa
        fields = [
            'id', 'tipo', 'razao_social', 'nome_fantasia', 'sigla', 'email_comercial',
            'telefone1', 'ativo', 'created_at', 'assinatura_ativa', 'plano_nome', 'situacao'
        ]

    def get_assinatura_ativa(self, obj):
        if obj.assinatura_ativa:
            return AssinaturaSerializer(obj.assinatura_ativa).data
        return None

    def get_plano_nome(self, obj):
        assinatura = obj.assinatura_ativa
        if assinatura:
            return assinatura.plano.nome
        return None

    def get_situacao(self, obj):
        # Empresa bloqueada
        if not obj.ativo:
            return 'Bloqueada'

        assinatura = obj.assinatura_ativa

        if not assinatura:
            return 'Sem plano'

        if assinatura.expirada or not assinatura.ativa:
            return 'Plano expirado'

        return 'Ativa'


# -------------------- Serializers adicionais --------------------


from django.contrib.auth import get_user_model


class PFUserAdminSerializer(serializers.ModelSerializer):
    """Serializer de leitura de usuários PF (com dados de perfil)."""

    name = serializers.CharField(source='person_profile.name', read_only=True)
    cpf = serializers.CharField(source='person_profile.cpf', read_only=True)
    phone = serializers.CharField(source='person_profile.phone', read_only=True)

    class Meta:
        model = get_user_model()
        fields = [
            'id', 'email', 'username', 'name', 'cpf', 'phone', 'created_at', 'is_superuser', 'is_staff'
        ]


class PFUserAdminWriteSerializer(serializers.Serializer):
    """Serializer para criação/edição de usuários PF no painel admin."""

    # Dados do usuário principal
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, required=False)
    username = serializers.CharField()

    # Dados opcionais do perfil PF
    name = serializers.CharField(required=False, allow_blank=True)

    # Permissões administrativas
    is_superuser = serializers.BooleanField(required=False, default=True)
    is_staff = serializers.BooleanField(required=False, default=True)

    def create(self, validated_data):
        # Cria diretamente o usuário superuser/staff
        User = get_user_model()
        user = User.objects.create_user(
            email=validated_data['email'],
            username=validated_data['username'],
            password=validated_data['password'],
            user_type='PF',
            is_staff=True,
            is_superuser=True if validated_data.get('is_superuser') else False,
        )

        from accounts.models import PersonProfile
        PersonProfile.objects.create(
            user=user,
            name=validated_data.get('name', '') or user.username,
            cpf=None,
            phone=None,
            position='Admin'
        )

        # Criar notificação
        try:
            from .notificacoes_utils import criar_notificacao_usuario_criado
            criar_notificacao_usuario_criado(user)
        except ImportError:
            pass  # Se o módulo não estiver disponível, apenas ignora

        return user

    def update(self, instance, validated_data):
        """Atualiza apenas email e senha do usuário existente."""
        User = get_user_model()
        
        # Atualiza email se fornecido
        if 'email' in validated_data:
            new_email = validated_data['email']
            # Verifica se o email já existe em outro usuário
            if User.objects.filter(email=new_email).exclude(id=instance.id).exists():
                raise serializers.ValidationError("E-mail já está em uso por outro usuário.")
            instance.email = new_email
        
        # Atualiza senha apenas se o usuário for admin (is_staff ou is_superuser)
        if 'password' in validated_data and validated_data['password']:
            # Verifica se o usuário atual (que está fazendo a requisição) é admin
            request = self.context.get('request')
            if request and request.user:
                if request.user.is_staff or request.user.is_superuser:
                    instance.set_password(validated_data['password'])
                else:
                    raise serializers.ValidationError("Apenas administradores podem alterar senhas de usuários.")
            else:
                raise serializers.ValidationError("Usuário não autenticado.")
        
        instance.save()
        return instance

    def validate_email(self, value):
        User = get_user_model()
        # Para criação, verifica se email já existe
        if not self.instance:  # Se não é uma atualização
            if User.objects.filter(email=value).exists():
                raise serializers.ValidationError("E-mail já cadastrado.")
        return value

    def validate_username(self, value):
        User = get_user_model()
        # Para criação, verifica se username já existe
        if not self.instance:  # Se não é uma atualização
            if User.objects.filter(username=value).exists():
                raise serializers.ValidationError("Username já está em uso.")
        return value

    class Meta:
        fields = ['id', 'email', 'password', 'username', 'name', 'is_superuser', 'is_staff']


# --------------------- Assinaturas ---------------------


from assinaturas.models import Assinatura, Plano, HistoricoPagamento
from django.utils.text import slugify


class AssinaturaAdminSerializer(serializers.ModelSerializer):
    empresa_nome = serializers.SerializerMethodField()
    plano_nome = serializers.SerializerMethodField()
    preco = serializers.DecimalField(source='plano.preco', max_digits=10, decimal_places=2, read_only=True)
    empresa_ativo = serializers.BooleanField(source='empresa.ativo', read_only=True)

    class Meta:
        model = Assinatura
        fields = [
            'id', 'empresa', 'empresa_nome', 'empresa_ativo', 'plano', 'plano_nome', 'preco', 'inicio', 'fim', 'ativa', 'expirada', 'observacoes', 'criado_em'
        ]

    def get_empresa_nome(self, obj):
        empresa = obj.empresa
        return empresa.nome_fantasia or getattr(empresa, 'razao_social', None) or empresa.sigla or str(empresa)

    def get_plano_nome(self, obj):
        return obj.plano.nome if obj.plano else None


class HistoricoPagamentoSerializer(serializers.ModelSerializer):
    tipo_display = serializers.CharField(source='get_tipo_display', read_only=True)
    plano_anterior_nome = serializers.CharField(source='plano_anterior.nome', read_only=True)
    plano_novo_nome = serializers.CharField(source='plano_novo.nome', read_only=True)
    usuario_admin_nome = serializers.CharField(source='usuario_admin.username', read_only=True)
    criado_em_formatado = serializers.SerializerMethodField()

    class Meta:
        model = HistoricoPagamento
        fields = [
            'id', 'tipo', 'tipo_display', 'descricao', 'plano_anterior', 'plano_anterior_nome',
            'plano_novo', 'plano_novo_nome', 'data_inicio_anterior', 'data_fim_anterior',
            'data_inicio_nova', 'data_fim_nova', 'dias_adicional', 'valor_anterior',
            'valor_novo', 'usuario_admin', 'usuario_admin_nome', 'criado_em', 'criado_em_formatado', 'observacoes'
        ]

    def get_criado_em_formatado(self, obj):
        return obj.criado_em.strftime('%d/%m/%Y %H:%M') if obj.criado_em else None


# --------------------- Planos ---------------------


class PlanoAdminSerializer(serializers.ModelSerializer):
    codigo = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = Plano
        fields = ['id', 'codigo', 'nome', 'preco', 'duracao_dias', 'ativo']

    def create(self, validated_data):
        if not validated_data.get('codigo'):
            validated_data['codigo'] = slugify(validated_data['nome'])[:20].upper()
        return super().create(validated_data)


# --------------------- Notificações ---------------------


class NotificacaoAdminSerializer(serializers.ModelSerializer):
    """Serializer para notificações do admin"""
    
    empresa_nome = serializers.CharField(source='empresa.nome_fantasia', read_only=True)
    usuario_nome = serializers.CharField(source='usuario.get_full_name', read_only=True)
    tempo_decorrido = serializers.SerializerMethodField()
    tipo_display = serializers.CharField(source='get_tipo_display', read_only=True)
    prioridade_display = serializers.CharField(source='get_prioridade_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = NotificacaoAdmin
        fields = [
            'id', 'tipo', 'tipo_display', 'titulo', 'mensagem', 'prioridade', 
            'prioridade_display', 'status', 'status_display', 'empresa', 'empresa_nome',
            'usuario', 'usuario_nome', 'dados_extras', 'criado_em', 'lida_em', 
            'tempo_decorrido'
        ]
        read_only_fields = ['criado_em', 'lida_em']
    
    def get_tempo_decorrido(self, obj):
        """Retorna o tempo decorrido desde a criação da notificação"""
        from django.utils import timezone
        from datetime import timedelta
        
        agora = timezone.now()
        diferenca = agora - obj.criado_em
        
        if diferenca.days > 0:
            return f"{diferenca.days} dia(s) atrás"
        elif diferenca.seconds > 3600:
            horas = diferenca.seconds // 3600
            return f"{horas} hora(s) atrás"
        elif diferenca.seconds > 60:
            minutos = diferenca.seconds // 60
            return f"{minutos} minuto(s) atrás"
        else:
            return "Agora mesmo" 