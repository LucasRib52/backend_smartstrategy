from django.urls import path
from . import views

app_name = 'usuariospainel'

urlpatterns = [
    # Listar e criar vínculos
    path('links/', views.UserCompanyLinkListView.as_view(), name='link-list'),
    path('links/create/', views.UserCompanyLinkCreateView.as_view(), name='link-create'),
    
    # Detalhes, atualização e deleção de vínculos
    path('links/<uuid:pk>/', views.UserCompanyLinkDetailView.as_view(), name='link-detail'),
    
    # Aceitar/Rejeitar convites
    path('links/<uuid:pk>/accept/', views.UserCompanyLinkAcceptView.as_view(), name='link-accept'),
    path('links/<uuid:pk>/reject/', views.UserCompanyLinkRejectView.as_view(), name='link-reject'),
    
    # Ativar/Desativar vínculos
    path('links/<uuid:pk>/toggle-status/', views.UserCompanyLinkToggleStatusView.as_view(), name='link-toggle-status'),
] 