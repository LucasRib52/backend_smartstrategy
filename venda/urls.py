from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import VendaViewSet

app_name = 'venda'

router = DefaultRouter()
router.register(r'', VendaViewSet)

urlpatterns = router.urls
