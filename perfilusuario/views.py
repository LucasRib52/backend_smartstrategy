from django.shortcuts import render
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth.models import User
from .models import PerfilUsuario
from django.core.files.storage import default_storage
from django.conf import settings
import os

# Create your views here.

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def obter_perfil(request):
    try:
        perfil = PerfilUsuario.objects.get(usuario=request.user)
        foto_url = request.build_absolute_uri(perfil.foto.url) if perfil.foto else None
        if hasattr(request.user, 'person_profile') and request.user.user_type == 'PF':
            nome_completo = request.user.person_profile.name or request.user.get_full_name() or request.user.username
        elif hasattr(request.user, 'company_profile') and request.user.user_type == 'PJ':
            nome_completo = request.user.company_profile.responsible_name or request.user.company_profile.company_name or request.user.get_full_name() or request.user.username
        else:
            nome_completo = request.user.get_full_name() or request.user.username
        return Response({
            'email': request.user.email,
            'foto': foto_url,
            'nome_completo': nome_completo,
            'user_type': request.user.user_type
        })
    except PerfilUsuario.DoesNotExist:
        return Response({
            'email': request.user.email,
            'foto': None,
            'nome_completo': request.user.get_full_name() or request.user.username,
            'user_type': request.user.user_type
        })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_foto(request):
    if 'foto' not in request.FILES:
        return Response({'error': 'Nenhuma foto enviada'}, status=status.HTTP_400_BAD_REQUEST)

    foto = request.FILES['foto']
    perfil, created = PerfilUsuario.objects.get_or_create(usuario=request.user)

    # Remove a foto antiga se existir
    if perfil.foto:
        try:
            os.remove(os.path.join(settings.MEDIA_ROOT, str(perfil.foto)))
        except:
            pass

    perfil.foto = foto
    perfil.save()

    return Response({
        'foto_url': request.build_absolute_uri(perfil.foto.url)
    })

@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def atualizar_email(request):
    novo_email = request.data.get('email')
    if not novo_email:
        return Response({'error': 'Email não fornecido'}, status=status.HTTP_400_BAD_REQUEST)

    if User.objects.filter(email=novo_email).exclude(id=request.user.id).exists():
        return Response({'error': 'Email já está em uso'}, status=status.HTTP_400_BAD_REQUEST)

    request.user.email = novo_email
    request.user.save()
    return Response({'message': 'Email atualizado com sucesso'})

@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def atualizar_senha(request):
    nova_senha = request.data.get('senha')
    if not nova_senha:
        return Response({'error': 'Senha não fornecida'}, status=status.HTTP_400_BAD_REQUEST)

    request.user.set_password(nova_senha)
    request.user.save()
    return Response({'message': 'Senha atualizada com sucesso'})

@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def atualizar_nome(request):
    user = request.user
    novo_nome = request.data.get('nome_completo')
    print(f"[DEBUG] Requisição para atualizar nome: user={user}, user_type={user.user_type}, novo_nome={novo_nome}")
    if not novo_nome:
        print("[DEBUG] Nome não fornecido")
        return Response({'error': 'Nome não fornecido'}, status=status.HTTP_400_BAD_REQUEST)
    if hasattr(user, 'person_profile') and user.user_type == 'PF':
        print(f"[DEBUG] Atualizando nome do perfil PF: antes={user.person_profile.name}")
        user.person_profile.name = novo_nome
        user.person_profile.save()
        print(f"[DEBUG] Nome atualizado para: {user.person_profile.name}")
        return Response({'message': 'Nome atualizado com sucesso', 'nome_completo': user.person_profile.name})
    elif hasattr(user, 'company_profile') and user.user_type == 'PJ':
        print(f"[DEBUG] Atualizando nome do responsável PJ: antes={user.company_profile.responsible_name}")
        user.company_profile.responsible_name = novo_nome
        user.company_profile.save()
        print(f"[DEBUG] Nome do responsável atualizado para: {user.company_profile.responsible_name}")
        return Response({'message': 'Nome do responsável atualizado com sucesso', 'nome_completo': user.company_profile.responsible_name})
    else:
        print("[DEBUG] Perfil não encontrado")
        return Response({'error': 'Perfil não encontrado'}, status=status.HTTP_400_BAD_REQUEST)
