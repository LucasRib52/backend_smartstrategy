from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PlanoViewSet

router = DefaultRouter()
router.register('planos', PlanoViewSet)

urlpatterns = router.urls 