from django.shortcuts import render
from rest_framework import viewsets, permissions
from .models import Plano
from .serializers import PlanoSerializer

# Create your views here.

class PlanoViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Plano.objects.all()
    serializer_class = PlanoSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = None

    def get_queryset(self):
        return Plano.objects.filter(ativo=True).order_by('nome')
