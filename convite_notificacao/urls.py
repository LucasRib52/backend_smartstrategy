from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ConviteUsuarioViewSet

router = DefaultRouter()
router.register(r'convites', ConviteUsuarioViewSet, basename='convite')

urlpatterns = [
    path('', include(router.urls)),
] 