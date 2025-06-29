from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    AdminMetricsAPIView, 
    AdminAnalyticsAPIView, 
    AdminDashboardAPIView, 
    EmpresaAdminViewSet, 
    PFUserAdminViewSet, 
    AssinaturaAdminViewSet, 
    PlanoAdminViewSet,
    NotificacaoAdminViewSet
)

router = DefaultRouter()
router.register('empresas', EmpresaAdminViewSet, basename='admin-empresas')
router.register('usuarios-pf', PFUserAdminViewSet, basename='admin-usuarios-pf')
router.register('pagamentos', AssinaturaAdminViewSet, basename='admin-pagamentos')
router.register('planos', PlanoAdminViewSet, basename='admin-planos')
router.register('notificacoes', NotificacaoAdminViewSet, basename='admin-notificacoes')

urlpatterns = [
    path('metrics/', AdminMetricsAPIView.as_view(), name='admin-metrics'),
    path('analytics/', AdminAnalyticsAPIView.as_view(), name='admin-analytics'),
    path('dashboard/', AdminDashboardAPIView.as_view(), name='admin-dashboard'),
]

urlpatterns += router.urls 