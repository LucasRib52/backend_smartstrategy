from django.urls import path
from .views import (
    AsaasWebhookView,
    AsaasWebhookTestView,
    AsaasCustomerView,
    AsaasSubscriptionView,
    AsaasWebhookListView,
    AsaasSimulateSubscriptionView
)

app_name = 'asaas'

urlpatterns = [
    path('webhooks/', AsaasWebhookView.as_view(), name='webhook'),
    path('webhooks/test/', AsaasWebhookTestView.as_view(), name='webhook_test'),
    path('customers/', AsaasCustomerView.as_view(), name='customer'),
    path('subscriptions/', AsaasSubscriptionView.as_view(), name='subscription'),
    path('subscriptions/<str:subscription_id>/', AsaasSubscriptionView.as_view(), name='subscription_detail'),
    path('webhooks/list/', AsaasWebhookListView.as_view(), name='webhook_list'),
    path('simulate/subscription/', AsaasSimulateSubscriptionView.as_view(), name='simulate_subscription'),
] 