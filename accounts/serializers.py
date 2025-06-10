from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import PersonProfile, CompanyProfile
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from empresas.models import Empresa
from usuariospainel.models import UserCompanyLink
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'email', 'username', 'user_type')
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
    trade_name = serializers.CharField()
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

    def validate_cnpj(self, value):
        if CompanyProfile.objects.filter(cnpj=value).exists():
            raise serializers.ValidationError("Este CNPJ já está cadastrado no sistema.")
        return value

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
            profile = CompanyProfile.objects.create(
                user=user,
                company_name=validated_data['company_name'],
                trade_name=validated_data['trade_name'],
                cnpj=validated_data['cnpj'],
                state_registration=validated_data.get('state_registration', ''),
                municipal_registration=validated_data['municipal_registration'],
                responsible_name=validated_data['responsible_name'],
                phone1=validated_data['phone1'],
                phone2=validated_data.get('phone2', ''),
                website=validated_data.get('website', '')
            )

            # --- CRIAÇÃO AUTOMÁTICA DA EMPRESA NO MODELO PRINCIPAL ---
            # Garante que toda empresa PJ criada no cadastro já aparece em empresas_empresa
            empresa, created = Empresa.objects.get_or_create(
                email_comercial=validated_data['email'],
                defaults={
                    'tipo': 'PJ',
                    'nome_fantasia': validated_data['trade_name'],
                    'sigla': validated_data['trade_name'][:10],
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
                empresa.nome_fantasia = validated_data['trade_name']
                empresa.sigla = validated_data['trade_name'][:10]
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
            # Se algo der errado, remove o usuário se ele foi criado
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
        
        # Adiciona o ID da empresa atual
        if user.user_type == 'PJ':
            logger.info(f"[TOKEN] Buscando empresa para PJ: {user.email}")
            # Se é PJ, busca a empresa pelo email
            try:
                empresa = Empresa.objects.get(email_comercial=user.email)
                logger.info(f"[TOKEN] Empresa encontrada: {empresa.id} - {empresa.nome_fantasia}")
                token['empresa_id'] = empresa.id
                # Atualiza a empresa_atual do usuário
                user.empresa_atual = empresa
                user.save()
                logger.info(f"[TOKEN] Token gerado com empresa_id: {token.get('empresa_id')}")
                logger.info(f"[TOKEN] Token completo: {token}")
            except Empresa.DoesNotExist:
                logger.error(f"[TOKEN] Empresa não encontrada pelo email: {user.email}")
                # Se não encontrou pelo email, tenta pelo empresa_atual
                if user.empresa_atual:
                    logger.info(f"[TOKEN] Usando empresa_atual: {user.empresa_atual.id}")
                    token['empresa_id'] = user.empresa_atual.id
                else:
                    logger.error(f"[TOKEN] Nenhuma empresa encontrada para PJ: {user.email}")
                    token['empresa_id'] = None
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