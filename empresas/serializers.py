from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Empresa, Endereco, Logomarca, Parametros, Responsavel
import re

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email']

class EnderecoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Endereco
        fields = '__all__'

    def validate_cep(self, value):
        if not re.match(r'^\d{8}$', value):
            raise serializers.ValidationError('CEP deve conter 8 dígitos numéricos')
        return value

class LogomarcaSerializer(serializers.ModelSerializer):
    imagem = serializers.SerializerMethodField()

    class Meta:
        model = Logomarca
        fields = '__all__'
        read_only_fields = ['data_upload']

    def get_imagem(self, obj):
        request = self.context.get('request')
        if obj.imagem and hasattr(obj.imagem, 'url'):
            url = obj.imagem.url
            if request is not None:
                return request.build_absolute_uri(url)
            return url
        return None

    def validate_imagem(self, value):
        if value:
            # Validar o tamanho do arquivo (máximo 5MB)
            if value.size > 5 * 1024 * 1024:
                raise serializers.ValidationError("O arquivo deve ter no máximo 5MB")
            
            # Validar o tipo do arquivo
            if not value.content_type.startswith('image/'):
                raise serializers.ValidationError("O arquivo deve ser uma imagem")
            
            # Validar a extensão
            if not value.name.lower().endswith(('.png', '.jpg', '.jpeg')):
                raise serializers.ValidationError("O arquivo deve ser PNG, JPG ou JPEG")
        
        return value

class ParametrosSerializer(serializers.ModelSerializer):
    class Meta:
        model = Parametros
        fields = '__all__'

    def validate_cor_primaria(self, value):
        if not re.match(r'^#[0-9A-Fa-f]{6}$', value):
            raise serializers.ValidationError('Cor deve estar no formato hexadecimal (#RRGGBB)')
        return value

    def validate_cor_secundaria(self, value):
        if not re.match(r'^#[0-9A-Fa-f]{6}$', value):
            raise serializers.ValidationError('Cor deve estar no formato hexadecimal (#RRGGBB)')
        return value

    def validate_cor_terciaria(self, value):
        if not re.match(r'^#[0-9A-Fa-f]{6}$', value):
            raise serializers.ValidationError('Cor deve estar no formato hexadecimal (#RRGGBB)')
        return value

class ResponsavelSerializer(serializers.ModelSerializer):
    usuario = UserSerializer(read_only=True)
    usuario_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source='usuario',
        write_only=True
    )

    class Meta:
        model = Responsavel
        fields = ['id', 'empresa', 'usuario', 'usuario_id', 'tipo', 'emails_financeiro', 'celular_financeiro', 'created_at', 'updated_at']
        read_only_fields = ['empresa']

    def validate(self, data):
        # Se estiver atualizando, não precisa validar o tipo
        if self.instance:
            return data

        # Se estiver criando, verifica se já existe um responsável do mesmo tipo
        empresa = self.context.get('empresa')
        tipo = data.get('tipo')
        
        if empresa and tipo:
            if Responsavel.objects.filter(empresa=empresa, tipo=tipo).exists():
                raise serializers.ValidationError(f'Já existe um responsável do tipo {tipo} para esta empresa')
        
        return data

class EmpresaSerializer(serializers.ModelSerializer):
    endereco = EnderecoSerializer(read_only=True)
    logomarca = LogomarcaSerializer(read_only=True)
    parametros = ParametrosSerializer(read_only=True)
    responsaveis = ResponsavelSerializer(many=True, read_only=True)

    class Meta:
        model = Empresa
        fields = [
            'id', 'tipo', 'nome_fantasia', 'sigla', 'cnpj', 'cpf', 'razao_social',
            'inscricao_estadual', 'inscricao_municipal', 'registro_crmv_uf',
            'registro_crmv_numero', 'email_comercial', 'telefone1', 'telefone2',
            'telefone3', 'site', 'redes_sociais', 'horario_funcionamento',
            'endereco', 'logomarca', 'parametros', 'responsaveis',
            'created_at', 'updated_at'
        ]

    def validate_cnpj(self, value):
        if not re.match(r'^\d{14}$', value):
            raise serializers.ValidationError('CNPJ deve conter 14 dígitos numéricos')
        return value

    def validate_telefone1(self, value):
        if not re.match(r'^\d{10,11}$', value):
            raise serializers.ValidationError('Telefone deve conter 10 ou 11 dígitos numéricos')
        return value

    def validate_email_comercial(self, value):
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', value):
            raise serializers.ValidationError('Email inválido')
        return value 