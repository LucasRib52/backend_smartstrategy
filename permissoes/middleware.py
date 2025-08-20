from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse
from usuariospainel.models import UserCompanyLink
from .models import ModuloPermissao
import logging

logger = logging.getLogger(__name__)

class PermissaoMiddleware(MiddlewareMixin):
    """
    Middleware para verificar permissões de acesso aos módulos
    """
    def process_request(self, request):
        # URLs públicas que não precisam de permissão
        urls_publicas = [
            '/api/accounts/token/',
            '/api/accounts/token/refresh/',
            '/api/accounts/token/verify/',
            '/api/accounts/register/',
            '/api/accounts/register/person/',
            '/api/accounts/register/company/',
            '/api/accounts/register/person-empresarial/',
            '/api/accounts/send-verification-code/',
            '/api/accounts/verify-code/',
            '/api/accounts/forgot-password/',
            '/api/accounts/reset-password/',
            '/api/auth/',
            '/api/accounts/login/',
            '/api/accounts/logout/',
            '/api/accounts/profile/',
            '/api/perfil/',
            '/api/usuarios/links/',
            '/api/usuarios/links/accept/',
            '/api/usuarios/links/reject/',
            '/api/selecionarperfilpf/',
            '/api/empresa_pessoafisica/',
            '/api/convite_notificacao/',
            '/api/permissoes/',
            '/api/dashboard/',
            '/admin/',
            '/api/admin/',
        ]

        # Se a URL é pública, permite o acesso sem verificar permissão
        if request.path in urls_publicas or any(request.path.startswith(url) for url in urls_publicas):
            logger.info(f"[PERMISSAO] URL {request.path} é pública")
            return None

        # Se o usuário não está autenticado, deixa o DRF lidar com isso
        if not request.user.is_authenticated:
            logger.info(f"[PERMISSAO] Usuário não autenticado para {request.path}")
            return None

        logger.info(f"[PERMISSAO] Processando requisição para {request.path}")
        logger.info(f"[PERMISSAO] Usuário: {request.user.email} (tipo: {request.user.user_type})")

        # Se o usuário é superusuário, acesso total
        if request.user.is_superuser:
            logger.info("[PERMISSAO] Superusuário — acesso total")
            return None

        # Se o usuário é PJ ou PFE, tem acesso total
        if request.user.user_type in ('PJ', 'PFE'):
            logger.info(f"[PERMISSAO] Usuário {request.user.user_type} tem acesso total")
            return None

        # Se não tiver empresa definida no request, permite o acesso
        if not hasattr(request, 'empresa') or not request.empresa:
            logger.warning(f"[PERMISSAO] Usuário {request.user.email} não tem empresa definida no request")
            return None

        # Obtém o módulo da URL
        modulo_codigo = self._get_modulo_from_url(request.path)
        if not modulo_codigo:
            logger.info(f"[PERMISSAO] URL {request.path} não requer verificação de módulo")
            return None

        # Verifica se o módulo existe
        modulo = ModuloPermissao.get_modulo_by_codigo(modulo_codigo)
        if not modulo:
            logger.warning(f"[PERMISSAO] Módulo {modulo_codigo} não encontrado")
            return None

        logger.info(f"[PERMISSAO] Verificando permissão para módulo: {modulo_codigo}")

        # Verifica se o usuário tem permissão para o módulo
        try:
            user_link = UserCompanyLink.objects.get(
                user=request.user,
                empresa=request.empresa,
                status='accepted'
            )
            
            # Garante que permissions seja um dicionário
            if not isinstance(user_link.permissions, dict):
                user_link.permissions = {'modulos': {}}
                user_link.save()
            
            # Garante que modulos exista em permissions
            if 'modulos' not in user_link.permissions:
                user_link.permissions['modulos'] = {}
                user_link.save()
            
            # Verifica se o usuário tem permissão para o módulo
            permissoes = user_link.permissions.get('modulos', {})
            if not permissoes.get(modulo_codigo, False):
                logger.warning(f"[PERMISSAO] Usuário {request.user.email} não tem permissão para módulo {modulo_codigo}")
                return JsonResponse({
                    'error': f'Você não tem permissão para acessar o módulo {modulo.nome}. Entre em contato com o administrador da empresa para solicitar acesso.',
                    'status': 'permission_denied'
                }, status=403)

            logger.info(f"[PERMISSAO] Usuário {request.user.email} tem permissão para módulo {modulo_codigo}")

        except UserCompanyLink.DoesNotExist:
            logger.warning(f"[PERMISSAO] Vínculo não encontrado para usuário {request.user.email} e empresa {request.empresa.id}")
            return JsonResponse({
                'error': 'Vínculo com a empresa não encontrado',
                'status': 'link_not_found'
            }, status=403)

        return None

    def _get_modulo_from_url(self, path):
        """
        Extrai o código do módulo da URL
        Exemplo: /api/marketing/... -> marketing
        """
        parts = path.strip('/').split('/')
        if len(parts) >= 2:
            modulo = parts[1].lower()
            # Só verifica permissão para marketing e financeiro
            if modulo in ['vendas', 'marketing']:
                return 'marketing'
            if modulo in ['financeiro']:
                return 'financeiro'
            # Para outros módulos, retorna None (não precisa verificar permissão)
            return None
        return None 