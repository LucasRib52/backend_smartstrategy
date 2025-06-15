from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_protect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.middleware.csrf import get_token
import logging

logger = logging.getLogger(__name__)

@api_view(['GET'])
@permission_classes([AllowAny])
@ensure_csrf_cookie
def csrf_view(request):
    """
    View para obter o token CSRF
    """
    try:
        token = get_token(request)
        return Response({
            'message': 'CSRF cookie set',
            'csrfToken': token
        })
    except Exception as e:
        logger.error(f'Erro ao definir cookie CSRF: {str(e)}')
        return Response(
            {'error': 'Erro interno do servidor'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([AllowAny])
@csrf_protect
def login_view(request):
    """
    View para autenticação de usuários usando email
    """
    try:
        email = request.data.get('email')
        password = request.data.get('password')

        if not email or not password:
            return Response(
                {'error': 'Por favor, forneça email e senha'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Busca o usuário pelo email
        User = get_user_model()
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            logger.warning(f'Tentativa de login falhou: email {email} não encontrado')
            return Response(
                {'error': 'Credenciais inválidas'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Tenta autenticar o usuário
        user = authenticate(request, username=user.username, password=password)

        if user is not None:
            login(request, user)
            logger.info(f'Usuário {email} fez login com sucesso')
            return Response({
                'message': 'Login realizado com sucesso',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email
                }
            })
        else:
            logger.warning(f'Tentativa de login falhou para o email {email}')
            return Response(
                {'error': 'Credenciais inválidas'},
                status=status.HTTP_401_UNAUTHORIZED
            )
    except Exception as e:
        logger.error(f'Erro durante o login: {str(e)}')
        return Response(
            {'error': 'Erro interno do servidor'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@login_required
@csrf_protect
def logout_view(request):
    """
    View para logout de usuários
    """
    try:
        logout(request)
        logger.info(f'Usuário {request.user.email} fez logout com sucesso')
        return Response({'message': 'Logout realizado com sucesso'})
    except Exception as e:
        logger.error(f'Erro durante o logout: {str(e)}')
        return Response(
            {'error': 'Erro interno do servidor'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@login_required
def user_view(request):
    """
    View para obter informações do usuário atual
    """
    try:
        user = request.user
        return Response({
            'id': user.id,
            'username': user.username,
            'email': user.email
        })
    except Exception as e:
        logger.error(f'Erro ao obter informações do usuário: {str(e)}')
        return Response(
            {'error': 'Erro interno do servidor'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([AllowAny])
@csrf_protect
def register_view(request):
    """
    View para registro de novos usuários
    """
    try:
        data = request.data
        email = data.get('email')
        password = data.get('password')
        name = data.get('name')

        # Validações básicas
        if not email or not password or not name:
            return Response(
                {'error': 'Por favor, forneça email, senha e nome'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Verifica se o email já está em uso
        User = get_user_model()
        if User.objects.filter(email=email).exists():
            return Response(
                {'error': 'Este email já está em uso'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Cria o novo usuário
        user = User.objects.create_user(
            username=email,  # Usa o email como username
            email=email,
            password=password
        )
        
        # Atualiza o nome do usuário
        user.first_name = name
        user.save()

        # Faz login do usuário após o registro
        login(request, user)
        
        logger.info(f'Novo usuário registrado com email: {email}')
        
        return Response({
            'message': 'Usuário registrado com sucesso',
            'user': {
                'id': user.id,
                'name': user.first_name,
                'email': user.email
            }
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        logger.error(f'Erro durante o registro: {str(e)}')
        return Response(
            {'error': 'Erro interno do servidor'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        ) 