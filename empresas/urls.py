from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import EmpresaViewSet, EnderecoViewSet, MinhaEmpresaAPIView

router = DefaultRouter()
router.register(r'empresas', EmpresaViewSet)
router.register(r'enderecos', EnderecoViewSet)

urlpatterns = [
    path('empresas/minha/', MinhaEmpresaAPIView.as_view(), name='minha-empresa'),
]
urlpatterns += router.urls 