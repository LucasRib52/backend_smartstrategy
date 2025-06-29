from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from usuariospainel.models import UserCompanyLink
from empresas.models import Empresa
from empresas.serializers import EmpresaSerializer

# Create your views here.

class EmpresasVinculadasPFView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.user_type != 'PF':
            return Response({'detail': 'Apenas usuários PF podem acessar.'}, status=403)
        
        # Busca todas as empresas vinculadas ao usuário PF
        links = UserCompanyLink.objects.filter(
            user=request.user
        ).select_related('empresa')
        
        # Prepara os dados das empresas com informações adicionais
        empresas_data = []
        for link in links:
            empresa_data = EmpresaSerializer(link.empresa, context={'request': request}).data
            empresa_data['cargo'] = link.position
            empresa_data['status'] = link.status
            empresa_data['is_active'] = link.status == 'accepted'
            empresa_data['link_id'] = str(link.id)
            empresas_data.append(empresa_data)
        
        return Response(empresas_data)
