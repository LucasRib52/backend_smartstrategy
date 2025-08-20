from django.urls import path
from rest_framework_simplejwt.views import (
    TokenRefreshView,
    TokenVerifyView,
)
from .views import (
    CustomTokenObtainPairView,
    RegisterPersonView, RegisterCompanyView, RegisterPersonEmpresarialView,
    UserProfileView,
    SendVerificationCodeView, VerifyCodeView, ForgotPasswordView, ResetPasswordView,
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
    path('register/person-empresarial/', RegisterPersonEmpresarialView.as_view(), name='register_person_empresarial'),
    path('profile/', UserProfileView.as_view(), name='profile'),

    # Verificação e recuperação
    path('send-verification-code/', SendVerificationCodeView.as_view(), name='send_verification_code'),
    path('verify-code/', VerifyCodeView.as_view(), name='verify_code'),
    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot_password'),
    path('reset-password/', ResetPasswordView.as_view(), name='reset_password'),
] 