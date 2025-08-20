from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import (
    CategoriaViewSet,
    InfluencerViewSet,
    LojaViewSet,
    LojaParceiraViewSet,
    ProdutoViewSet,
    VendaViewSet,
    PostViewSet,
    ClickViewSet,
    VisitaInfluencerViewSet,
    PublicLojaView,
)


router = DefaultRouter()
router.register(r"categorias", CategoriaViewSet, basename="categoria")
router.register(r"lojas", LojaViewSet, basename="loja")
router.register(r"lojas-parceiras", LojaParceiraViewSet, basename="loja-parceira")
router.register(r"produtos", ProdutoViewSet, basename="produto")
router.register(r"vendas", VendaViewSet, basename="venda")
router.register(r"posts", PostViewSet, basename="post")
router.register(r"cliques", ClickViewSet, basename="clique")
router.register(r"visitas", VisitaInfluencerViewSet, basename="visita")
router.register(r"", InfluencerViewSet, basename="influencer")


urlpatterns = [
    path("lojas/publica/<slug:slug>/", PublicLojaView.as_view(), name="public-loja-detail"),
    path("", include(router.urls)),
]


