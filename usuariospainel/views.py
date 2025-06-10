from django.shortcuts import render
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from rest_framework_simplejwt.authentication import JWTAuthentication
from .models import UserCompanyLink
from .serializers import (
    UserCompanyLinkSerializer,
    CreateUserCompanyLinkSerializer,
    UpdateUserCompanyLinkSerializer
)

# Create your views here.

class IsCompanyOwner(IsAuthenticated):
    """
    Permissão personalizada para verificar se o usuário é dono da empresa
    """
    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.user_type == 'PJ'

class UserCompanyLinkListView(generics.ListAPIView):
    """
    View para listar todos os vínculos de usuários de uma empresa
    """
    serializer_class = UserCompanyLinkSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get_queryset(self):
        print(f"[VIEW] Usuário: {self.request.user.email} (tipo: {self.request.user.user_type})")
        print(f"[VIEW] Empresa ID: {getattr(self.request, 'empresa_id', None)}")
        print(f"[VIEW] Empresa Atual: {getattr(self.request.user, 'empresa_atual', None)}")

        if self.request.user.user_type == 'PJ':
            if hasattr(self.request, 'empresa_id'):
                return UserCompanyLink.objects.filter(empresa_id=self.request.empresa_id)
            if self.request.user.empresa_atual:
                return UserCompanyLink.objects.filter(empresa=self.request.user.empresa_atual)
            return UserCompanyLink.objects.none()
        # Para PF, retorna apenas o link ativo
        return UserCompanyLink.objects.filter(
            user=self.request.user,
            status='accepted'
        ).first()

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        
        # Se for PF, retorna o objeto único
        if request.user.user_type == 'PF':
            if not queryset:
                return Response({'error': 'Nenhum vínculo ativo encontrado'}, status=404)
            serializer = self.get_serializer(queryset)
            return Response(serializer.data)
            
        # Se for PJ, retorna a lista
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

class UserCompanyLinkCreateView(generics.CreateAPIView):
    """
    View para criar um novo vínculo entre usuário e empresa
    """
    serializer_class = CreateUserCompanyLinkSerializer
    permission_classes = [IsCompanyOwner]
    authentication_classes = [JWTAuthentication]

    def perform_create(self, serializer):
        if not self.request.user.empresa_atual:
            raise PermissionError('Empresa não encontrada')
        serializer.save()

class UserCompanyLinkDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    View para visualizar, atualizar e deletar um vínculo específico
    """
    serializer_class = UserCompanyLinkSerializer
    permission_classes = [IsCompanyOwner]
    authentication_classes = [JWTAuthentication]

    def get_queryset(self):
        if hasattr(self.request, 'empresa_id'):
            return UserCompanyLink.objects.filter(empresa_id=self.request.empresa_id)
        if self.request.user.empresa_atual:
            return UserCompanyLink.objects.filter(empresa=self.request.user.empresa_atual)
        return UserCompanyLink.objects.none()

class UserCompanyLinkAcceptView(APIView):
    """
    View para aceitar um convite de vínculo
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request, pk):
        link = get_object_or_404(UserCompanyLink, pk=pk, user=request.user)
        
        if link.is_expired():
            return Response(
                {'error': 'O convite expirou'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if link.status != 'pending':
            return Response(
                {'error': 'Este convite já foi processado'},
                status=status.HTTP_400_BAD_REQUEST
            )

        link.status = 'accepted'
        link.save()

        return Response(
            {'message': 'Convite aceito com sucesso'},
            status=status.HTTP_200_OK
        )

class UserCompanyLinkRejectView(APIView):
    """
    View para rejeitar um convite de vínculo
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request, pk):
        link = get_object_or_404(UserCompanyLink, pk=pk, user=request.user)
        
        if link.status != 'pending':
            return Response(
                {'error': 'Este convite já foi processado'},
                status=status.HTTP_400_BAD_REQUEST
            )

        link.status = 'rejected'
        link.save()

        return Response(
            {'message': 'Convite rejeitado com sucesso'},
            status=status.HTTP_200_OK
        )

class UserCompanyLinkToggleStatusView(APIView):
    """
    View para ativar/desativar um vínculo
    """
    permission_classes = [IsCompanyOwner]
    authentication_classes = [JWTAuthentication]

    def post(self, request, pk):
        empresa_id = getattr(request, 'empresa_id', None)
        if not empresa_id and request.user.empresa_atual:
            empresa_id = request.user.empresa_atual.id
            
        if not empresa_id:
            return Response(
                {'error': 'Empresa não encontrada'},
                status=status.HTTP_404_NOT_FOUND
            )
            
        link = get_object_or_404(UserCompanyLink, pk=pk, empresa_id=empresa_id)
        
        if link.status == 'rejected':
            return Response(
                {'error': 'Não é possível alterar o status de um vínculo recusado'},
                status=status.HTTP_400_BAD_REQUEST
            )

        link.status = 'inactive' if link.status == 'accepted' else 'accepted'
        link.save()

        return Response(
            {'message': f'Status alterado para {link.status}'},
            status=status.HTTP_200_OK
        )
