from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from usuariospainel.models import UserCompanyLink
from .models import ModuloPermissao
from .serializers import ModuloPermissaoSerializer, UserPermissaoSerializer
from django.contrib.auth import get_user_model
import uuid
import logging
from django.http import Http404

logger = logging.getLogger(__name__)
User = get_user_model()

class ModuloPermissaoViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gerenciar os módulos disponíveis
    """
    queryset = ModuloPermissao.objects.filter(ativo=True)
    serializer_class = ModuloPermissaoSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        Retorna apenas os módulos ativos
        """
        return ModuloPermissao.get_modulos_ativos()

class UserPermissaoViewSet(viewsets.ViewSet):
    """
    ViewSet para gerenciar as permissões dos usuários
    """
    permission_classes = [IsAuthenticated]

    def _get_user_link(self, link_id):
        """
        Obtém o vínculo do usuário com a empresa atual usando o ID do vínculo
        """
        try:
            # Descobre a empresa em contexto (middleware define request.empresa / empresa_id)
            empresa_contexto = getattr(self.request, 'empresa', None) or getattr(self.request.user, 'empresa_atual', None)

            if not empresa_contexto:
                logger.error(f"Usuário {self.request.user.email} não tem empresa definida no contexto")
                return Response(
                    {'error': 'Usuário não tem empresa definida'},
                    status=status.HTTP_401_UNAUTHORIZED
                )

            # Tenta converter para UUID primeiro
            try:
                if isinstance(link_id, str):
                    link_id = uuid.UUID(link_id)
            except ValueError:
                # Se não for UUID, tenta buscar pelo ID numérico do usuário
                try:
                    user_id = int(link_id)
                    link = get_object_or_404(
                        UserCompanyLink,
                        user_id=user_id,
                        empresa=empresa_contexto,
                        status='accepted'
                    )
                    logger.info(f"Vínculo encontrado para usuário {user_id} na empresa {empresa_contexto.id}")
                    return link
                except ValueError:
                    logger.error(f"ID inválido: {link_id}")
                    return Response(
                        {'error': 'ID inválido'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # Busca o UserCompanyLink usando o UUID do vínculo
            link = get_object_or_404(
                UserCompanyLink,
                id=link_id,
                empresa=empresa_contexto,
                status='accepted'
            )
            logger.info(f"Vínculo encontrado com UUID {link_id} na empresa {empresa_contexto.id}")
            return link

        except UserCompanyLink.DoesNotExist:
            logger.error(f"Vínculo não encontrado para ID {link_id} na empresa {empresa_contexto.id if empresa_contexto else 'N/A'}")
            return Response(
                {'error': 'Vínculo não encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Http404:
            logger.error(f"Vínculo não encontrado (Http404) para ID {link_id} na empresa {empresa_contexto.id if empresa_contexto else 'N/A'}")
            return Response(
                {'error': 'Vínculo não encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Erro ao buscar vínculo: {str(e)}")
            return Response(
                {'error': f'Erro ao buscar vínculo: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def list(self, request):
        """
        Lista as permissões de todos os usuários da empresa
        """
        user_links = UserCompanyLink.objects.filter(
            empresa=request.user.empresa_atual,
            status='accepted'
        )
        serializer = UserPermissaoSerializer(user_links, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        """
        Obtém as permissões de um usuário específico
        """
        user_link = self._get_user_link(pk)
        if isinstance(user_link, Response):
            return user_link
        serializer = UserPermissaoSerializer(user_link)
        return Response(serializer.data)

    def update(self, request, pk=None):
        """
        Atualiza as permissões de um usuário
        """
        user_link = self._get_user_link(pk)
        if isinstance(user_link, Response):
            return user_link
        
        # Garante que o campo permissions seja um dicionário
        if not isinstance(user_link.permissions, dict):
            user_link.permissions = {}
        
        # Atualiza apenas as permissões dos módulos
        permissoes_atualizadas = {
            'modulos': request.data.get('permissions', {}).get('modulos', {})
        }
        
        # Atualiza as permissões
        user_link.permissions = permissoes_atualizadas
        user_link.save()

        serializer = UserPermissaoSerializer(user_link)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def modulos_disponiveis(self, request, pk=None):
        """
        Lista os módulos disponíveis para um vínculo
        """
        try:
            # Busca o vínculo usando o ID
            user_link = self._get_user_link(pk)
            if isinstance(user_link, Response):
                return user_link
            
            # Obtém os módulos ativos
            modulos = ModuloPermissao.get_modulos_ativos()
            
            # Garante que o campo permissions tenha a estrutura correta
            if not isinstance(user_link.permissions, dict):
                user_link.permissions = {'modulos': {}}
                user_link.save()
            
            # Obtém as permissões dos módulos, garantindo que seja um dicionário
            permissoes = user_link.permissions.get('modulos', {})
            if not isinstance(permissoes, dict):
                permissoes = {}
                user_link.permissions['modulos'] = permissoes
                user_link.save()
            
            # Cria a lista de módulos com suas permissões
            modulos_data = []
            for modulo in modulos:
                modulos_data.append({
                    'codigo': modulo.codigo,
                    'nome': modulo.nome,
                    'descricao': modulo.descricao,
                    # Aqui retorna o valor granular salvo
                    'tem_permissao': permissoes.get(modulo.codigo, '')
                })
            
            return Response(modulos_data)
            
        except Exception as e:
            import traceback
            print(f"Erro em modulos_disponiveis: {str(e)}")
            print(traceback.format_exc())
            return Response(
                {'error': f'Erro ao obter módulos disponíveis: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
