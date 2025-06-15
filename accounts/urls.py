from django.urls import path
from rest_framework_simplejwt.views import (
    TokenRefreshView,
    TokenVerifyView,
)
from .views import (
    CustomTokenObtainPairView,
    RegisterPersonView, RegisterCompanyView,
    UserProfileView
)

app_name = 'accounts'

urlpatterns = [
    # URLs de autenticação JWT
    path('token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    
    # URLs de registro e perfil
    path('register/person/', RegisterPersonView.as_view(), name='register_person'),
    path('register/company/', RegisterCompanyView.as_view(), name='register_company'),
    path('profile/', UserProfileView.as_view(), name='profile'),
] 