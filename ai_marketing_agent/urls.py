from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import MarketingDataViewSet, FileUploadViewSet

router = DefaultRouter()
router.register(r'marketing-data', MarketingDataViewSet, basename='marketing-data')
router.register(r'file-uploads', FileUploadViewSet, basename='file-upload')

urlpatterns = [
    path('', include(router.urls)),
] 