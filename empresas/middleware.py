from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
from .models import Empresa
from usuariospainel.models import UserCompanyLink
import logging
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
import uuid
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

logger = logging.getLogger(__name__)

class EmpresaMiddleware(MiddlewareMixin):
    def process_request(self, request):
        # Log inicial
        logger.info(f"[MIDDLEWARE] Processando request: {request.path}")
        
        # Lista de paths que não precisam de empresa
        no_company_paths = [
            '/api/accounts/token/',
            '/api/accounts/register/',
            '/api/accounts/register/person/',
            '/api/accounts/register/company/',
            '/api/accounts/register/person-empresarial/',
            '/api/accounts/verify-email/',
            '/api/accounts/reset-password/',
            '/api/accounts/reset-password/confirm/',
        ]
        
        if request.path in no_company_paths:
            logger.info(f"[MIDDLEWARE] Path não requer empresa: {request.path}")
            return None

        # Tenta autenticar usando o JWT
        jwt_auth = JWTAuthentication()
        try:
            auth_tuple = jwt_auth.authenticate(request)
            if auth_tuple is None:
                logger.info(f"[MIDDLEWARE] Usuário não autenticado: {request.path}")
                return None
            user, token = auth_tuple
            request.user = user  # Atualiza o request.user

            # Superusuário não precisa de empresa
            if user.is_superuser:
                logger.info("[MIDDLEWARE] Superusuário — bypass empresa")
                request.empresa = None
                return None

            logger.info(f"[MIDDLEWARE] Usuário autenticado: {user.email} (tipo: {user.user_type})")
            
            # Pega o empresa_id do token
            empresa_id = token.get('empresa_id')
            logger.info(f"[MIDDLEWARE] Token JWT - empresa_id: {empresa_id}")
            logger.info(f"[MIDDLEWARE] Token JWT - user_type: {token.get('user_type')}")
            logger.info(f"[MIDDLEWARE] Token JWT - email: {token.get('email')}")

            # Se tem empresa_id no token, tenta usar ele
            if empresa_id:
                try:
                    empresa = Empresa.objects.get(id=empresa_id)
                    logger.info(f"[MIDDLEWARE] Empresa encontrada pelo ID do token: {empresa_id}")
                    request.empresa = empresa
                    request.empresa_id = str(empresa.id)
                    return None
                except Empresa.DoesNotExist:
                    logger.error(f"[MIDDLEWARE] Empresa não encontrada pelo ID do token: {empresa_id}")

            # Se não encontrou pelo ID ou não tem ID, tenta pelo email
            if user.user_type in ('PJ', 'PFE'):
                try:
                    empresa = Empresa.objects.get(email_comercial=user.email)
                    logger.info(f"[MIDDLEWARE] Empresa PJ encontrada pelo email: {user.email}")
                    request.empresa = empresa
                    request.empresa_id = str(empresa.id)
                    return None
                except Empresa.DoesNotExist:
                    logger.error(f"[MIDDLEWARE] Empresa PJ não encontrada pelo email: {user.email}")
                    request.empresa = None
                    return None

            logger.warning(f"[MIDDLEWARE] Nenhuma empresa encontrada para o usuário {user.email}")
            request.empresa = None
            return None

        except Exception as e:
            logger.error(f"[MIDDLEWARE] Erro ao processar autenticação: {str(e)}")
            return None 