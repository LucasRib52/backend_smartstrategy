from rest_framework import status, generics
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.http import HttpRequest
from django.test.client import RequestFactory
import logging
from .serializers import (
    UserSerializer, PersonProfileSerializer, CompanyProfileSerializer,
    RegisterPersonSerializer, RegisterCompanySerializer, RegisterPersonEmpresarialSerializer,
    CustomTokenObtainPairSerializer,
    SendCodeSerializer, VerifyCodeSerializer, ForgotPasswordSerializer, ResetPasswordSerializer,
)
from empresas.models import Empresa
from usuariospainel.models import UserCompanyLink
# Importa perfis para criação automática quando inexistentes
from .models import PersonProfile, CompanyProfile
from django.contrib.auth.hashers import make_password
from .services.email_service import EmailService

logger = logging.getLogger(__name__)
User = get_user_model()

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        logger.info(f"[TOKEN] Tentativa de login para email: {request.data.get('email')}")
        
        # Primeiro valida as credenciais
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except Exception as e:
            logger.error(f"[TOKEN] Erro na validação: {str(e)}")
            return Response({'error': 'Credenciais inválidas'}, status=status.HTTP_401_UNAUTHORIZED)
        
        # Se chegou aqui, as credenciais são válidas
        user = serializer.user
        # Bloqueia login se email não estiver verificado (exceto superusuário)
        if not user.is_superuser and not getattr(user, 'email_verified', False):
            logger.warning(f"[TOKEN] Login bloqueado para {user.email}: email não verificado")
            return Response({'error': 'Email não verificado. Verifique seu e-mail e informe o código enviado.'}, status=status.HTTP_403_FORBIDDEN)
        response = Response(serializer.validated_data)
        
        # Define a empresa_atual do usuário
        try:
            # Se for superuser, ignora definição de empresa_atual
            if user.is_superuser:
                logger.info(f"[TOKEN] Superuser {user.email} não requer empresa_atual")
            elif user.user_type in ('PJ', 'PFE'):
                # Se é PJ, a própria empresa é a empresa_atual
                empresa = Empresa.objects.get(email_comercial=user.email)
                user.empresa_atual = empresa
                user.save()
                logger.info(f"[TOKEN] Usuário PJ/PFE é a própria empresa: {empresa} (ID: {empresa.id})")
            else:
                # Para PF, busca o vínculo ativo
                link = UserCompanyLink.objects.filter(
                    user=user,
                    status='accepted'
                ).first()
                if link:
                    user.empresa_atual = link.empresa
                    user.save()
                    logger.info(f"[TOKEN] Empresa definida para PF: {link.empresa} (ID: {link.empresa.id})")
        except Empresa.DoesNotExist:
            logger.error(f"[TOKEN] Empresa não encontrada para PJ: {user.email}")
            return Response({'error': 'Empresa não encontrada'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"[TOKEN] Erro ao definir empresa_atual: {str(e)}")
        
        # Adiciona dados do usuário e perfil
        user_serializer = UserSerializer(user)
        # Garante que sempre exista um perfil relacionado ao usuário
        if user.user_type == 'PF':
            profile, _ = PersonProfile.objects.get_or_create(
                user=user,
                defaults={
                    'name': user.get_full_name() or user.username or user.email
                }
            )
            profile_serializer = PersonProfileSerializer(profile)
        else:
            profile, _ = CompanyProfile.objects.get_or_create(
                user=user,
                defaults={
                    'company_name': user.username or 'Empresa Administradora'
                }
            )
            profile_serializer = CompanyProfileSerializer(profile)
        
        response.data.update({
            'user': user_serializer.data,
            'profile': profile_serializer.data
        })
        logger.info(f"[TOKEN] Login bem sucedido para usuário: {user.email}")
        
        return response

class RegisterPersonView(generics.CreateAPIView):
    """
    View para registro de pessoa física
    """
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = RegisterPersonSerializer

    def create(self, request, *args, **kwargs):
        # Store credentials before any request processing
        email = request.data.get('email')
        password = request.data.get('password')
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        created = serializer.save()
        # Não autentica automaticamente. Envia código e pede confirmação de e-mail
        try:
            user_obj = created if not isinstance(created, dict) else User.objects.get(email=email)
            EmailService.create_and_send_code(user=user_obj, code_type="registration")
        except Exception as e:
            logger.error(f"[REGISTER] Falha ao enviar e-mail de verificação: {e}")

        # Retorna instrução de verificação
        return Response({
            'success': True,
            'message': 'Conta criada! Enviamos um código de verificação para seu e-mail.'
        }, status=status.HTTP_201_CREATED)

class RegisterCompanyView(generics.CreateAPIView):
    """
    View para registro de pessoa jurídica
    """
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = RegisterCompanySerializer

    def create(self, request, *args, **kwargs):
        # Store credentials before any request processing
        email = request.data.get('email')
        password = request.data.get('password')
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        created = serializer.save()
        try:
            user_obj = created if not isinstance(created, dict) else User.objects.get(email=email)
            EmailService.create_and_send_code(user=user_obj, code_type="registration")
        except Exception as e:
            logger.error(f"[REGISTER] Falha ao enviar e-mail de verificação: {e}")

        # Retorna instrução de verificação
        return Response({
            'success': True,
            'message': 'Conta criada! Enviamos um código de verificação para seu e-mail.'
        }, status=status.HTTP_201_CREATED)


class RegisterPersonEmpresarialView(generics.CreateAPIView):
    """
    View para registro de pessoa física empresarial (mesmas permissões/fluxo de PJ, usando CPF)
    """
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = RegisterPersonEmpresarialSerializer

    def create(self, request, *args, **kwargs):
        email = request.data.get('email')
        password = request.data.get('password')

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        created = serializer.save()
        try:
            user_obj = created if not isinstance(created, dict) else User.objects.get(email=email)
            EmailService.create_and_send_code(user=user_obj, code_type="registration")
        except Exception as e:
            logger.error(f"[REGISTER] Falha ao enviar e-mail de verificação: {e}")

        return Response({
            'success': True,
            'message': 'Conta criada! Enviamos um código de verificação para seu e-mail.'
        }, status=status.HTTP_201_CREATED)

class SendVerificationCodeView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = SendCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        code_type = serializer.validated_data['code_type']

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({'error': 'Email não encontrado'}, status=status.HTTP_404_NOT_FOUND)

        EmailService.create_and_send_code(user=user, code_type=code_type)
        return Response({'success': True, 'message': 'Código enviado com sucesso'}, status=status.HTTP_200_OK)


class VerifyCodeView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = VerifyCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        code = serializer.validated_data['code']
        code_type = serializer.validated_data['code_type']

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({'error': 'Email não encontrado'}, status=status.HTTP_404_NOT_FOUND)

        # Para password_reset: apenas valida (não consome) o código aqui; consumo acontecerá no reset
        should_mark_used = False if code_type == 'password_reset' else True
        if EmailService.verify_code(user=user, code=code, code_type=code_type, mark_used=should_mark_used):
            if code_type == 'registration' and not user.email_verified:
                user.email_verified = True
                user.save(update_fields=['email_verified'])
            return Response({'success': True, 'message': 'Código verificado com sucesso'}, status=status.HTTP_200_OK)
        return Response({'error': 'Código inválido ou expirado'}, status=status.HTTP_400_BAD_REQUEST)


class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({'error': 'Email não encontrado'}, status=status.HTTP_404_NOT_FOUND)
        EmailService.create_and_send_code(user=user, code_type='password_reset')
        return Response({'success': True, 'message': 'Código de recuperação enviado'}, status=status.HTTP_200_OK)


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        code = serializer.validated_data['code']
        new_password = serializer.validated_data['new_password']

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({'error': 'Email não encontrado'}, status=status.HTTP_404_NOT_FOUND)

        # Aqui consome definitivamente o código
        if not EmailService.verify_code(user=user, code=code, code_type='password_reset', mark_used=True):
            return Response({'error': 'Código inválido ou expirado'}, status=status.HTTP_400_BAD_REQUEST)

        user.password = make_password(new_password)
        user.save(update_fields=['password'])
        return Response({'success': True, 'message': 'Senha redefinida com sucesso'}, status=status.HTTP_200_OK)

class UserProfileView(APIView):
    """
    View para obter informações do usuário logado
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            logger.info(f"[PROFILE] Requisição recebida. Headers: {request.headers}")
            logger.info(f"[PROFILE] Usuário autenticado: {request.user.is_authenticated}")
            logger.info(f"[PROFILE] Usuário: {request.user}")

            user = request.user
            if not user or not user.is_authenticated:
                logger.error("[PROFILE] Usuário não autenticado")
                return Response({'error': 'Usuário não autenticado'}, status=status.HTTP_401_UNAUTHORIZED)

            serializer = UserSerializer(user)
            
            # Garante que sempre exista um perfil
            if user.user_type == 'PF':
                profile, _ = PersonProfile.objects.get_or_create(
                    user=user,
                    defaults={
                        'name': user.get_full_name() or user.username or user.email
                    }
                )
                profile_serializer = PersonProfileSerializer(profile)
            else:
                profile, _ = CompanyProfile.objects.get_or_create(
                    user=user,
                    defaults={
                        'company_name': user.username or 'Empresa Administradora'
                    }
                )
                profile_serializer = CompanyProfileSerializer(profile)
            
            logger.info(f"[PROFILE] Perfil retornado com sucesso para: {user.email}")
            return Response({
                'user': serializer.data,
                'profile': profile_serializer.data
            })
        except Exception as e:
            logger.error(f"[PROFILE] Erro ao obter perfil: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
