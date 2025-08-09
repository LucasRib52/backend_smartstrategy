from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PlanoViewSet, subscription_status, simulate_payment_webhook, upgrade_subscription

router = DefaultRouter()
router.register('planos', PlanoViewSet)

urlpatterns = router.urls + [
    path('assinatura/status/', subscription_status, name='subscription-status'),
    path('assinaturas/upgrade/', upgrade_subscription, name='assinaturas-upgrade'),
    path('assinatura/simulate-webhook/', simulate_payment_webhook, name='simulate-payment-webhook'),
] 