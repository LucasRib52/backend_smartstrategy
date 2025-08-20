from django.shortcuts import render
from rest_framework import viewsets, status, views
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from .models import Empresa, Endereco, Logomarca, Responsavel
from .serializers import (
    EmpresaSerializer, EnderecoSerializer, LogomarcaSerializer,
    ResponsavelSerializer
)

User = get_user_model()

# Create your views here.

class EmpresaViewSet(viewsets.ModelViewSet):
    queryset = Empresa.objects.all()
    serializer_class = EmpresaSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        obj = get_object_or_404(self.get_queryset(), pk=self.kwargs["pk"])
        self.check_object_permissions(self.request, obj)
        return obj

    def create(self, request, *args, **kwargs):
        try:
            # Criar a empresa
            response = super().create(request, *args, **kwargs)
            
            # Se a criação foi bem sucedida, atualiza a empresa_atual do usuário
            if response.status_code == status.HTTP_201_CREATED:
                empresa = Empresa.objects.get(id=response.data['id'])
                user = request.user
                user.empresa_atual = empresa
                user.save()
            
            return response
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': 'Erro ao criar empresa'}, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        try:
            return super().update(request, *args, **kwargs)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': 'Erro ao atualizar empresa'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get', 'put'])
    def endereco(self, request, pk=None):
        try:
            empresa = self.get_object()
            endereco, created = Endereco.objects.get_or_create(empresa=empresa)

            if request.method == 'GET':
                serializer = EnderecoSerializer(endereco)
                return Response(serializer.data)

            serializer = EnderecoSerializer(endereco, data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get', 'put'])
    def logomarca(self, request, pk=None):
        try:
            empresa = self.get_object()
            logomarca, created = Logomarca.objects.get_or_create(empresa=empresa)

            if request.method == 'GET':
                serializer = LogomarcaSerializer(logomarca, context={'request': request})
                return Response(serializer.data)

            # Verificar se o arquivo foi enviado
            if 'imagem' not in request.FILES:
                return Response(
                    {'detail': 'Nenhum arquivo foi enviado'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Verificar o tamanho do arquivo
            if request.FILES['imagem'].size > 5 * 1024 * 1024:  # 5MB
                return Response(
                    {'detail': 'O arquivo deve ter no máximo 5MB'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Verificar o tipo do arquivo
            if not request.FILES['imagem'].content_type.startswith('image/'):
                return Response(
                    {'detail': 'O arquivo deve ser uma imagem'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Verificar a extensão
            if not request.FILES['imagem'].name.lower().endswith(('.png', '.jpg', '.jpeg')):
                return Response(
                    {'detail': 'O arquivo deve ser PNG, JPG ou JPEG'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Criar ou atualizar a logomarca
            if logomarca:
                # Se já existe, atualiza
                logomarca.imagem = request.FILES['imagem']
                logomarca.save()
                serializer = LogomarcaSerializer(logomarca, context={'request': request})
            else:
                # Se não existe, cria
                serializer = LogomarcaSerializer(data={
                    'empresa': empresa.id,
                    'imagem': request.FILES['imagem']
                }, context={'request': request})
                if serializer.is_valid():
                    serializer.save()
                else:
                    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            return Response(serializer.data)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get', 'post'])
    def responsaveis(self, request, pk=None):
        try:
            empresa = self.get_object()

            if request.method == 'GET':
                responsaveis = Responsavel.objects.filter(empresa=empresa)
                serializer = ResponsavelSerializer(responsaveis, many=True)
                return Response(serializer.data)

            serializer = ResponsavelSerializer(data=request.data, context={'empresa': empresa})
            if serializer.is_valid():
                serializer.save(empresa=empresa)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get', 'put', 'delete'], url_path='responsaveis/(?P<responsavel_id>[^/.]+)')
    def responsavel_detail(self, request, pk=None, responsavel_id=None):
        try:
            empresa = self.get_object()
            responsavel = get_object_or_404(Responsavel, empresa=empresa, id=responsavel_id)

            if request.method == 'GET':
                serializer = ResponsavelSerializer(responsavel)
                return Response(serializer.data)

            if request.method == 'PUT':
                serializer = ResponsavelSerializer(responsavel, data=request.data, context={'empresa': empresa})
                if serializer.is_valid():
                    serializer.save()
                    return Response(serializer.data)
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            if request.method == 'DELETE':
                responsavel.delete()
                return Response(status=status.HTTP_204_NO_CONTENT)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class EnderecoViewSet(viewsets.ModelViewSet):
    queryset = Endereco.objects.all()
    serializer_class = EnderecoSerializer

# Endpoint simples para retornar a empresa do usuário autenticado
class MinhaEmpresaAPIView(views.APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            empresa = getattr(request.user, 'empresa_atual', None)
            if not empresa:
                return Response({'detail': 'Empresa não encontrada'}, status=status.HTTP_404_NOT_FOUND)
            # Prefetch assinatura ativa com plano para reduzir queries
            empresa_qs = Empresa.objects.filter(id=empresa.id)
            from assinaturas.models import Assinatura
            from django.db.models import Prefetch
            empresa_qs = empresa_qs.prefetch_related(
                Prefetch(
                    'assinaturas',
                    queryset=Assinatura.objects.select_related('plano').order_by('-inicio'),
                )
            )
            empresa = empresa_qs.first() or empresa
            serializer = EmpresaSerializer(empresa, context={'request': request})
            return Response(serializer.data)
        except Exception as e:
            print(f"Erro no endpoint minha empresa: {str(e)}")
            import traceback
            traceback.print_exc()
            return Response({'error': 'Erro interno do servidor'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
