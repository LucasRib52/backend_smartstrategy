from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import PersonProfile, CompanyProfile
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from empresas.models import Empresa
from usuariospainel.models import UserCompanyLink
import logging
import re
import requests
from django.db import IntegrityError, transaction

logger = logging.getLogger(__name__)
User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    empresa_atual = serializers.PrimaryKeyRelatedField(read_only=True)
    class Meta:
        model = User
        fields = ('id', 'email', 'username', 'user_type', 'empresa_atual', 'is_superuser', 'is_staff')
        read_only_fields = ('id',)

class PersonProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = PersonProfile
        fields = ('id', 'user', 'name', 'cpf', 'phone', 'position', 'created_at', 'updated_at')
        read_only_fields = ('id', 'created_at', 'updated_at')

class CompanyProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = CompanyProfile
        fields = (
            'id', 'user', 'company_name', 'trade_name', 'cnpj', 
            'state_registration', 'municipal_registration', 'responsible_name',
            'phone1', 'phone2', 'website', 'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'created_at', 'updated_at')

class RegisterPersonSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    username = serializers.CharField()
    name = serializers.CharField()
    cpf = serializers.CharField()
    phone = serializers.CharField()
    position = serializers.CharField()

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Este email já está cadastrado no sistema.")
        return value

    def validate_cpf(self, value):
        if PersonProfile.objects.filter(cpf=value).exists():
            raise serializers.ValidationError("Este CPF já está cadastrado no sistema.")
        return value

    def create(self, validated_data):
        try:
            # Cria o usuário
            user = User.objects.create_user(
                email=validated_data['email'],
                username=validated_data['username'],
                password=validated_data['password'],
                user_type='PF'
            )
            
            # Cria o perfil de pessoa física
            profile = PersonProfile.objects.create(
                user=user,
                name=validated_data['name'],
                cpf=validated_data['cpf'],
                phone=validated_data['phone'],
                position=validated_data['position']
            )
            
            # Criar notificação
            try:
                from painel_admin.notificacoes_utils import criar_notificacao_usuario_criado
                criar_notificacao_usuario_criado(user)
            except ImportError:
                pass  # Se o módulo não estiver disponível, apenas ignora
            
            return {
                'user': UserSerializer(user).data,
                'profile': PersonProfileSerializer(profile).data
            }
        except Exception as e:
            # Se algo der errado, remove o usuário se ele foi criado
            if 'user' in locals():
                user.delete()
            raise e

class RegisterCompanySerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    username = serializers.CharField()
    company_name = serializers.CharField()
    trade_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    cnpj = serializers.CharField()
    state_registration = serializers.CharField(required=False, allow_blank=True)
    municipal_registration = serializers.CharField()
    responsible_name = serializers.CharField()
    phone1 = serializers.CharField()
    phone2 = serializers.CharField(required=False, allow_blank=True)
    website = serializers.URLField(required=False, allow_blank=True)

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Este email já está cadastrado no sistema.")
        return value

    @staticmethod
    def _is_valid_cnpj_digits(cnpj_num: str) -> bool:
        if len(cnpj_num) != 14 or len(set(cnpj_num)) == 1:
            return False
        def calc_dv(base, pesos):
            soma = sum(int(d) * p for d, p in zip(base, pesos))
            resto = soma % 11
            return '0' if resto < 2 else str(11 - resto)
        dv1 = calc_dv(cnpj_num[:12], [5,4,3,2,9,8,7,6,5,4,3,2])
        dv2 = calc_dv(cnpj_num[:13], [6,5,4,3,2,9,8,7,6,5,4,3,2])
        return cnpj_num[-2:] == dv1 + dv2

    def validate_cnpj(self, value):
        digits = re.sub(r'[^0-9]', '', value)

        if not digits.isdigit() or len(digits) != 14 or not self._is_valid_cnpj_digits(digits):
            raise serializers.ValidationError('CNPJ inválido (dígitos verificadores incorretos)')

        # Checar duplicidade (ignora pontuação)
        for existing in CompanyProfile.objects.values_list('cnpj', flat=True):
            if existing and re.sub(r'[^0-9]', '', existing) == digits:
                raise serializers.ValidationError("Este CNPJ já está cadastrado no sistema.")

        # Consulta BrasilAPI – bloqueia somente se 404/400
        try:
            resp = requests.get(f'https://brasilapi.com.br/api/cnpj/v1/{digits}', timeout=10)
            if resp.status_code in (404, 400):
                raise serializers.ValidationError("CNPJ não encontrado na Receita Federal (BrasilAPI)")
            # se 200 ok, outros status ignoramos (problema temporário)
        except requests.RequestException:
            pass  # erro rede -> segue

        # Formata para 00.000.000/0000-00 antes de prosseguir
        formatted = f"{digits[0:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:14]}"
        return formatted

    def create(self, validated_data):
        try:
            # Cria o usuário
            user = User.objects.create_user(
                email=validated_data['email'],
                username=validated_data['username'],
                password=validated_data['password'],
                user_type='PJ'
            )
            
            # Cria o perfil da empresa
            try:
                profile = CompanyProfile.objects.create(
                    user=user,
                    company_name=validated_data['company_name'],
                    trade_name=validated_data.get('trade_name', ''),
                    cnpj=validated_data['cnpj'],
                    state_registration=validated_data.get('state_registration', ''),
                    municipal_registration=validated_data['municipal_registration'],
                    responsible_name=validated_data['responsible_name'],
                    phone1=validated_data['phone1'],
                    phone2=validated_data.get('phone2', ''),
                    website=validated_data.get('website', '')
                )
            except IntegrityError:
                # Apaga o usuário que foi criado para manter consistência
                user.delete()
                raise serializers.ValidationError({"cnpj": ["Este CNPJ já está cadastrado no sistema."]})

            # --- CRIAÇÃO AUTOMÁTICA DA EMPRESA NO MODELO PRINCIPAL ---
            # Garante que toda empresa PJ criada no cadastro já aparece em empresas_empresa
            empresa, created = Empresa.objects.get_or_create(
                email_comercial=validated_data['email'],
                defaults={
                    'tipo': 'PJ',
                    'nome_fantasia': validated_data.get('trade_name', validated_data['company_name']),
                    'sigla': (validated_data.get('trade_name') or validated_data['company_name'])[:10],
                    'cnpj': validated_data['cnpj'],
                    'razao_social': validated_data['company_name'],
                    'inscricao_estadual': validated_data.get('state_registration', ''),
                    'inscricao_municipal': validated_data['municipal_registration'],
                    'telefone1': validated_data['phone1'],
                    'telefone2': validated_data.get('phone2', ''),
                    'site': validated_data.get('website', '')
                }
            )
            # Se já existe, pode atualizar os campos principais (opcional)
            if not created:
                empresa.nome_fantasia = validated_data.get('trade_name', '')
                empresa.sigla = (validated_data.get('trade_name') or validated_data['company_name'])[:10]
                empresa.cnpj = validated_data['cnpj']
                empresa.razao_social = validated_data['company_name']
                empresa.inscricao_estadual = validated_data.get('state_registration', '')
                empresa.inscricao_municipal = validated_data['municipal_registration']
                empresa.telefone1 = validated_data['phone1']
                empresa.telefone2 = validated_data.get('phone2', '')
                empresa.site = validated_data.get('website', '')
                empresa.save()
            # --------------------------------------------------------
            
            return {
                'user': UserSerializer(user).data,
                'profile': CompanyProfileSerializer(profile).data
            }
        except Exception as e:
            if 'user' in locals():
                user.delete()
            raise e 

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = 'email'  # Usa email ao invés de username

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        logger.info(f"[TOKEN] Gerando token para usuário: {user.email} (tipo: {user.user_type})")
        
        # Adiciona informações do usuário ao token
        token['email'] = user.email
        token['username'] = user.username
        token['user_type'] = user.user_type
        token['is_superuser'] = user.is_superuser
        
        # Se for superusuário (admin), não há necessidade de vincular empresa/perfil
        if user.is_superuser:
            logger.info("[TOKEN] Usuário é superusuário; pulando vinculação de empresa/perfil.")
            return token
        
        # Adiciona o ID da empresa atual
        if user.user_type == 'PJ':
            logger.info(f"[TOKEN] Buscando empresa para PJ: {user.email}")
            # Se é PJ, busca a empresa pelo email
            try:
                empresa = Empresa.objects.filter(email_comercial=user.email).first()
                if empresa:
                    logger.info(f"[TOKEN] Empresa encontrada: {empresa.id} - {empresa.nome_fantasia}")
                else:
                    raise Empresa.DoesNotExist
                token['empresa_id'] = empresa.id
                # Atualiza a empresa_atual do usuário
                user.empresa_atual = empresa
                user.save()
                logger.info(f"[TOKEN] Token gerado com empresa_id: {token.get('empresa_id')}")
                logger.info(f"[TOKEN] Token completo: {token}")
            except Empresa.DoesNotExist:
                logger.error(f"[TOKEN] Empresa não encontrada pelo email: {user.email}")
        else:
            # Para PF, busca o vínculo ativo
            try:
                link = UserCompanyLink.objects.filter(
                    user=user,
                    status='accepted'
                ).first()
                if link:
                    token['empresa_id'] = link.empresa.id
                    user.empresa_atual = link.empresa
                    user.save()
                    logger.info(f"[TOKEN] Empresa PF definida no token: {link.empresa.id}")
                else:
                    logger.warning(f"[TOKEN] Nenhum vínculo ativo encontrado para PF: {user.email}")
                    token['empresa_id'] = None
            except Exception as e:
                logger.error(f"[TOKEN] Erro ao buscar vínculo para PF: {str(e)}")
                token['empresa_id'] = None
        
        # Adiciona informações do perfil
        if user.user_type == 'PF':
            try:
                profile = user.person_profile
                token['profile'] = {
                    'name': profile.name,
                    'cpf': profile.cpf,
                    'phone': profile.phone,
                    'position': profile.position,
                }
            except:
                token['profile'] = None
        else:
            try:
                profile = user.company_profile
                token['profile'] = {
                    'company_name': profile.company_name,
                    'trade_name': profile.trade_name,
                    'cnpj': profile.cnpj,
                    'responsible_name': profile.responsible_name,
                }
            except:
                token['profile'] = None
        
        # Log final do token
        logger.info(f"[TOKEN] Token final gerado: {token}")
        return token 