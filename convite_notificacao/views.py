from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import ConviteUsuario
from .serializers import (
    ConviteUsuarioSerializer,
    AceitarConviteSerializer,
    RecusarConviteSerializer
)
from usuariospainel.models import UserCompanyLink
from empresas.models import Empresa

class ConviteUsuarioViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gerenciar convites de usuários
    """
    permission_classes = [IsAuthenticated]
    serializer_class = ConviteUsuarioSerializer
    queryset = ConviteUsuario.objects.all()

    def get_queryset(self):
        """
        Filtra os convites baseado no tipo de usuário
        """
        queryset = ConviteUsuario.objects.all()
        
        # Se for PJ, mostra apenas convites da empresa atual
        if self.request.user.user_type == 'PJ':
            empresa = self.request.user.empresa_atual
            if not empresa:
                return ConviteUsuario.objects.none()
            return queryset.filter(empresa=empresa)
        
        # Se for PF, retorna TODOS os convites para o email do usuário, independente do status
        return queryset.filter(email_convidado__iexact=self.request.user.email)

    def perform_create(self, serializer):
        """
        Cria um novo convite
        """
        # Apenas PJ pode criar convites
        if self.request.user.user_type != 'PJ':
            raise ValueError("Apenas usuários PJ podem enviar convites")
            
        empresa = self.request.user.empresa_atual
        if not empresa:
            raise ValueError("Empresa não encontrada. Por favor, selecione uma empresa primeiro.")
        serializer.save(empresa=empresa)

    @action(detail=True, methods=['post'])
    def aceitar(self, request, pk=None):
        """
        Aceita um convite OU um vínculo pendente
        """
        try:
            convite = self.get_object()
            serializer = AceitarConviteSerializer(data={}, context={'request': request})
            if serializer.is_valid():
                try:
                    convite.aceitar(request.user)
                    return Response({'status': 'convite aceito'})
                except ValueError as e:
                    return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            # Se não encontrar convite, tenta aceitar vínculo
            from usuariospainel.models import UserCompanyLink
            try:
                link = UserCompanyLink.objects.get(id=pk, user=request.user, status='pending')
                link.status = 'accepted'
                link.save()
                return Response({'status': 'vinculo aceito'})
            except UserCompanyLink.DoesNotExist:
                return Response({'error': 'Convite ou vínculo não encontrado'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['post'])
    def recusar(self, request, pk=None):
        """
        Recusa um convite
        """
        convite = self.get_object()
        serializer = RecusarConviteSerializer(data={}, context={'request': request})
        
        if serializer.is_valid():
            try:
                convite.recusar(request.user)
                return Response({'status': 'convite recusado'})
            except ValueError as e:
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def pendentes(self, request):
        """
        Lista convites pendentes ou vínculos pendentes do usuário PF
        """
        queryset = self.get_queryset()
        if queryset.exists():
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)
        # Se não houver convites, busca vínculos pendentes
        if request.user.user_type == 'PF':
            links = UserCompanyLink.objects.filter(user=request.user, status='pending')
            # Adapta para o formato esperado pelo frontend
            convites = []
            for link in links:
                convites.append({
                    'id': str(link.id),
                    'empresa_nome': link.empresa.nome_fantasia if hasattr(link.empresa, 'nome_fantasia') else '',
                    'empresa_razao_social': getattr(link.empresa, 'razao_social', ''),
                    'created_at': link.created_at,
                    'status': link.status,
                    'position': link.position,
                    'empresa': link.empresa.id,
                })
            return Response(convites)
        return Response([])
