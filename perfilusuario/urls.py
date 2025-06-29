from django.urls import path
from . import views

urlpatterns = [
    path('', views.obter_perfil, name='obter_perfil'),
    path('upload-foto/', views.upload_foto, name='upload_foto'),
    path('atualizar-email/', views.atualizar_email, name='atualizar_email'),
    path('atualizar-senha/', views.atualizar_senha, name='atualizar_senha'),
    path('atualizar-nome/', views.atualizar_nome, name='atualizar_nome'),
] 