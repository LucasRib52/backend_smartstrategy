from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from venda.views import VendaViewSet
from dashboard.views import DashboardAPIView, AllYearsDashboardAPIView, AvailableYearsAPIView
from django.conf import settings
from django.conf.urls.static import static

router = DefaultRouter()
router.register(r'vendas', VendaViewSet)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
    path('api/dashboard/', DashboardAPIView.as_view(), name='dashboard-api'),
    path('api/dashboard/all-years/', AllYearsDashboardAPIView.as_view(), name='all-years-dashboard-api'),
    path('api/dashboard/available-years/', AvailableYearsAPIView.as_view(), name='available-years-api'),
    
    # Rotas de empresas
    path('api/', include('empresas.urls')),
    
    # URLs do app accounts
    path('api/accounts/', include('accounts.urls')),
    
    # URLs do app usuariospainel
    path('api/usuarios/', include('usuariospainel.urls')),
    
    # URLs do app convite_notificacao
    path('api/convite_notificacao/', include('convite_notificacao.urls')),
    
    # URLs do app selecionarperfilpf
    path('api/selecionarperfilpf/', include('selecionarperfilpf.urls')),
    
    # URLs do app perfil
    path('api/perfil/', include('perfilusuario.urls')),
    
    # Novo app
    path('api/empresa_pessoafisica/', include('empresa_pessoafisica.urls')),
    
    # URLs do app permissoes
    path('api/permissoes/', include('permissoes.urls')),
    
    # URLs do app ai_marketing_agent
    path('api/ai-marketing/', include('ai_marketing_agent.urls')),
    
    # URLs do app painel_admin
    path('api/admin/', include('painel_admin.urls')),
    
    # Planos
    path('api/', include('assinaturas.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
