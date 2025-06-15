from django.urls import path
from .views import EmpresasVinculadasPFView

urlpatterns = [
    path('empresas/', EmpresasVinculadasPFView.as_view(), name='empresas-vinculadas-pf'),
] 