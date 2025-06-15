from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken
from usuariospainel.models import UserCompanyLink
from empresas.models import Empresa
from .serializers import EmpresaSerializer
import logging

logger = logging.getLogger(__name__)

# Create your views here.

class EmpresasVinculadasPFView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.user_type != 'PF':
            return Response({'detail': 'Apenas usuários PF podem acessar.'}, status=403)
        links = UserCompanyLink.objects.filter(user=request.user, status='accepted').select_related('empresa')
        empresas = []
        for link in links:
            empresa = link.empresa
            setattr(empresa, 'position', link.position)
            empresas.append(empresa)
        serializer = EmpresaSerializer(empresas, many=True, context={'request': request})
        return Response(serializer.data)

class SelecionarEmpresaView(APIView):
    """
    View para listar empresas disponíveis para o usuário PF
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        if request.user.user_type != 'PF':
            return Response({'detail': 'Apenas usuários PF podem acessar.'}, status=403)

        # Busca empresas vinculadas ao usuário
        links = UserCompanyLink.objects.filter(user=request.user, status='accepted').select_related('empresa')
        # Anexa o cargo (position) ao objeto empresa para serialização
        empresas = []
        for link in links:
            empresa = link.empresa
            # Adiciona atributo dinamicamente para o serializer capturar
            setattr(empresa, 'position', link.position)
            empresas.append(empresa)
        serializer = EmpresaSerializer(empresas, many=True, context={'request': request})
        return Response(serializer.data)

class SelecionarEmpresaJWTView(APIView):
    """
    View para selecionar uma empresa e atualizar o token JWT
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        if request.user.user_type != 'PF':
            return Response({'detail': 'Apenas usuários PF podem acessar.'}, status=403)

        empresa_id = request.data.get('empresa_id')
        if not empresa_id:
            return Response({'detail': 'empresa_id é obrigatório.'}, status=400)
        
        try:
            empresa = Empresa.objects.get(id=empresa_id)
            UserCompanyLink.objects.get(user=request.user, empresa=empresa, status='accepted')
            print(f"[PF] Usuário {request.user.email} selecionou empresa {empresa.id} - {empresa.nome_fantasia}")
        except (Empresa.DoesNotExist, UserCompanyLink.DoesNotExist):
            return Response({'detail': 'Empresa não encontrada ou sem permissão.'}, status=404)
        
        # Atualiza o token JWT com a nova empresa
        refresh = RefreshToken.for_user(request.user)
        refresh['empresa_id'] = str(empresa.id)
        
        # Atualiza o campo empresa_atual do usuário para refletir a escolha
        request.user.empresa_atual = empresa
        request.user.save(update_fields=["empresa_atual"])
        
        return Response({
            'detail': 'Empresa selecionada com sucesso.',
            'access': str(refresh.access_token),
            'refresh': str(refresh)
        })
