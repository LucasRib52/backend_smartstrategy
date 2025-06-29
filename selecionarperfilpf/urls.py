from django.urls import path
from . import views

app_name = 'selecionarperfilpf'

urlpatterns = [
    path('empresas/', views.SelecionarEmpresaView.as_view(), name='listar_empresas'),
    path('set-empresa/', views.SelecionarEmpresaJWTView.as_view(), name='selecionar_empresa'),
] 