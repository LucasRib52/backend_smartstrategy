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
    RegisterPersonSerializer, RegisterCompanySerializer,
    CustomTokenObtainPairSerializer
)
from empresas.models import Empresa
from usuariospainel.models import UserCompanyLink
# Importa perfis para criação automática quando inexistentes
from .models import PersonProfile, CompanyProfile

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
        response = Response(serializer.validated_data)
        
        # Define a empresa_atual do usuário
        try:
            # Se for superuser, ignora definição de empresa_atual
            if user.is_superuser:
                logger.info(f"[TOKEN] Superuser {user.email} não requer empresa_atual")
            elif user.user_type == 'PJ':
                # Se é PJ, a própria empresa é a empresa_atual
                empresa = Empresa.objects.get(email_comercial=user.email)
                user.empresa_atual = empresa
                user.save()
                logger.info(f"[TOKEN] Usuário PJ é a própria empresa: {empresa} (ID: {empresa.id})")
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
    serializer_class = RegisterPersonSerializer

    def create(self, request, *args, **kwargs):
        # Store credentials before any request processing
        email = request.data.get('email')
        password = request.data.get('password')
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Cria uma nova requisição para o token usando as credenciais armazenadas
        factory = RequestFactory()
        token_request = factory.post('/api/accounts/token/', {
            'email': email,
            'password': password
        })
        token_request.user = user
        
        # Gera token JWT para o novo usuário
        token_view = CustomTokenObtainPairView.as_view()
        token_response = token_view(token_request)
        
        if token_response.status_code == 200:
            return Response(token_response.data, status=status.HTTP_201_CREATED)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class RegisterCompanyView(generics.CreateAPIView):
    """
    View para registro de pessoa jurídica
    """
    permission_classes = [AllowAny]
    serializer_class = RegisterCompanySerializer

    def create(self, request, *args, **kwargs):
        # Store credentials before any request processing
        email = request.data.get('email')
        password = request.data.get('password')
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Cria uma nova requisição para o token usando as credenciais armazenadas
        factory = RequestFactory()
        token_request = factory.post('/api/accounts/token/', {
            'email': email,
            'password': password
        })
        token_request.user = user
        
        # Gera token JWT para o novo usuário
        token_view = CustomTokenObtainPairView.as_view()
        token_response = token_view(token_request)
        
        if token_response.status_code == 200:
            return Response(token_response.data, status=status.HTTP_201_CREATED)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

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
