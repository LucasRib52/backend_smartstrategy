from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'modulos', views.ModuloPermissaoViewSet, basename='modulo')
router.register(r'usuarios', views.UserPermissaoViewSet, basename='usuario-permissao')

# URLs adicionais para ações personalizadas
urlpatterns = [
    path('', include(router.urls)),
    # Adiciona explicitamente a rota para modulos_disponiveis
    path('usuarios/<uuid:pk>/modulos_disponiveis/', 
         views.UserPermissaoViewSet.as_view({'get': 'modulos_disponiveis'}), 
         name='usuario-modulos-disponiveis'),
] 