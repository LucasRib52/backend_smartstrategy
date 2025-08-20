from rest_framework import viewsets, permissions, filters, status, generics
from rest_framework.response import Response
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Sum, Q, Count
from django.utils import timezone
from datetime import timedelta
from .models import Categoria, Influencer, Loja, LojaParceira, Produto, Venda, Post, Click, VisitaInfluencer
from .serializers import (
    CategoriaSerializer,
    InfluencerSerializer,
    LojaSerializer,
    LojaParceiraSerializer,
    ProdutoSerializer,
    VendaSerializer,
    PostSerializer,
    ClickSerializer,
    VisitaInfluencerSerializer
)


class BasePermission(permissions.IsAuthenticated):
    def has_object_permission(self, request, view, obj):
        if hasattr(obj, "influencer"):
            influencer = obj.influencer
        elif isinstance(obj, Influencer):
            influencer = obj
        else:
            return super().has_object_permission(request, view, obj)
        return influencer.usuario_id == request.user.id or request.user.is_staff


class PublicLojaView(generics.RetrieveAPIView):
    queryset = Loja.objects.filter(status="ativo")
    serializer_class = LojaSerializer
    lookup_field = 'slug'
    permission_classes = [permissions.AllowAny]

    def retrieve(self, request, *args, **kwargs):
        loja = self.get_object()
        loja_data = self.get_serializer(loja).data
        
        # Produtos ativos do influencer
        produtos_qs = Produto.objects.filter(influencer=loja.influencer, status="ativo").order_by('-data_cadastro')
        produtos_data = ProdutoSerializer(produtos_qs, many=True, context={'request': request}).data

        # Lojas parceiras ordenadas por cliques (mais clicadas primeiro)
        lojas_parceiras_qs = loja.influencer.lojas_parceiras.filter(status='ativo').annotate(
            num_cliques=Count('cliques')
        ).order_by('-num_cliques', '-data_cadastro')
        lojas_parceiras_data = LojaParceiraSerializer(lojas_parceiras_qs, many=True, context={'request': request}).data

        return Response({
            "loja": loja_data,
            "produtos": produtos_data,
            "lojas_parceiras": lojas_parceiras_data, # Agora vem ordenado
        })


class CategoriaViewSet(viewsets.ModelViewSet):
    queryset = Categoria.objects.all()
    serializer_class = CategoriaSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["nome", "descricao"]
    ordering = ["nome"]

    def get_queryset(self):
        user = self.request.user
        return Categoria.objects.filter(Q(criador=user) | Q(criador__isnull=True))

    def perform_create(self, serializer):
        serializer.save(criador=self.request.user)


class InfluencerViewSet(viewsets.ModelViewSet):
    serializer_class = InfluencerSerializer
    permission_classes = [BasePermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["status", "categoria_principal"]
    search_fields = ["nome_artistico", "usuario__email"]
    ordering = ["-data_cadastro"]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Influencer.objects.all()
        return Influencer.objects.filter(usuario=user)

    def perform_create(self, serializer):
        serializer.save(usuario=self.request.user)

    @action(detail=False, methods=["get"], url_path="me")
    def me(self, request):
        try:
            influencer = Influencer.objects.get(usuario=request.user)
        except Influencer.DoesNotExist:
            # Criar influencer automaticamente se não existir
            influencer = Influencer.objects.create(
                usuario=request.user,
                nome_artistico=request.user.get_full_name() or request.user.username,
                status="ativo"
            )
        
        serializer = self.get_serializer(influencer)
        return Response(serializer.data)

    @action(detail=True, methods=["get"], url_path="dashboard")
    def dashboard(self, request, pk=None):
        influencer = self.get_object()
        
        # Estatísticas de vendas
        total_vendas = Venda.objects.filter(influencer=influencer).aggregate(
            total=Sum("preco_total"), quantidade=Sum("quantidade"), comissao=Sum("comissao")
        )
        total_clientes = (
            Venda.objects.filter(influencer=influencer)
            .values("cliente_email")
            .distinct()
            .count()
        )
        produtos_ativos = influencer.produtos.filter(status="ativo").count()
        
        # Estatísticas de visitas
        from datetime import date
        hoje = date.today()
        inicio_mes = hoje.replace(day=1)
        
        visitas_hoje = influencer.visitas.filter(data_visita_date=hoje).count()
        visitas_mes = influencer.visitas.filter(data_visita_date__gte=inicio_mes).count()
        visitas_total = influencer.visitas.count()
        
        # Visitas por dispositivo (últimos 30 dias)
        inicio_30_dias = hoje - timedelta(days=30)
        visitas_por_dispositivo = influencer.visitas.filter(
            data_visita_date__gte=inicio_30_dias
        ).values('device_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Visitas por dia (últimos 7 dias)
        inicio_7_dias = hoje - timedelta(days=7)
        visitas_por_dia = influencer.visitas.filter(
            data_visita_date__gte=inicio_7_dias
        ).values('data_visita_date').annotate(
            count=Count('id')
        ).order_by('data_visita_date')
        
        return Response(
            {
                "total_vendas": total_vendas["total"] or 0,
                "total_quantidade": total_vendas["quantidade"] or 0,
                "total_comissao": total_vendas["comissao"] or 0,
                "total_clientes": total_clientes,
                "produtos_ativos": produtos_ativos,
                "visitas_hoje": visitas_hoje,
                "visitas_mes": visitas_mes,
                "visitas_total": visitas_total,
                "visitas_por_dispositivo": list(visitas_por_dispositivo),
                "visitas_por_dia": list(visitas_por_dia),
            }
        )

    @action(detail=True, methods=["get"], url_path="estatisticas")
    def estatisticas(self, request, pk=None):
        influencer = self.get_object()
        return Response(
            {
                "lojas": influencer.lojas.count(),
                "produtos": influencer.produtos.count(),
                "vendas": influencer.vendas.count(),
                "posts": influencer.posts.count(),
            }
        )

    # Lojas publicadas (1 por influencer)
    @action(detail=True, methods=["get", "post"], url_path="lojas")
    def lojas(self, request, pk=None):
        influencer = self.get_object()
        if request.method.lower() == "post":
            # Limite de 1 loja por influencer
            if influencer.lojas.exists():
                return Response({"error": "Você já possui uma loja publicada. Limite de 1 loja por usuário."}, status=status.HTTP_400_BAD_REQUEST)
            data = request.data.copy()
            data["influencer"] = str(influencer.id)
            serializer = LojaSerializer(data=data)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)
        qs = influencer.lojas.all().order_by("-data_cadastro")
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = LojaSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = LojaSerializer(qs, many=True)
        return Response(serializer.data)

    # (end) lojas publicadas

    @action(detail=True, methods=["get", "post"], url_path="produtos")
    def produtos(self, request, pk=None):
        influencer = self.get_object()
        if request.method.lower() == "post":
            data = request.data.copy()
            data["influencer"] = str(influencer.id)
            serializer = ProdutoSerializer(data=data, context={'request': request})
            serializer.is_valid(raise_exception=True)
            produto = serializer.save()
            return Response(ProdutoSerializer(produto, context={'request': request}).data)
        qs = influencer.produtos.all().order_by("-data_cadastro")
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = ProdutoSerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        serializer = ProdutoSerializer(qs, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=["get", "post"], url_path="vendas")
    def vendas(self, request, pk=None):
        influencer = self.get_object()
        if request.method.lower() == "post":
            data = request.data.copy()
            data["influencer"] = str(influencer.id)
            serializer = VendaSerializer(data=data)
            serializer.is_valid(raise_exception=True)
            venda = serializer.save()
            return Response(VendaSerializer(venda).data)
        qs = influencer.vendas.all().order_by("-data_venda")
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = VendaSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = VendaSerializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"], url_path="vendas/relatorio")
    def vendas_relatorio(self, request, pk=None):
        influencer = self.get_object()
        qs = influencer.vendas.all()
        agg = qs.aggregate(total=Sum("preco_total"), qtd=Sum("quantidade"), com=Sum("comissao"))
        total_vendas = agg.get('total') or 0
        total_quantidade = agg.get('qtd') or 0
        total_comissao = agg.get('com') or 0
        return Response({
            "total_vendas": total_vendas,
            "total_quantidade": total_quantidade,
            "total_comissao": total_comissao,
        })

    # Faturas removidas do módulo influencer

    @action(detail=True, methods=["get", "post"], url_path="posts")
    def posts(self, request, pk=None):
        influencer = self.get_object()
        if request.method.lower() == "post":
            data = request.data.copy()
            data["influencer"] = str(influencer.id)
            serializer = PostSerializer(data=data)
            serializer.is_valid(raise_exception=True)
            post = serializer.save()
            return Response(PostSerializer(post).data)
        qs = influencer.posts.all().order_by("-data_geracao")
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = PostSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = PostSerializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="posts/gerar")
    def posts_gerar(self, request, pk=None):
        influencer = self.get_object()
        plataforma = request.data.get("plataforma", "instagram")
        conteudo = request.data.get("conteudo")
        produto_id = request.data.get("produto")
        if not conteudo:
            conteudo = f"Post automático para {plataforma}."
        post = Post.objects.create(
            influencer=influencer,
            produto_id=produto_id,
            plataforma=plataforma,
            conteudo=conteudo,
        )
        serializer = PostSerializer(post)
        return Response(serializer.data)

    @action(detail=True, methods=["get"], url_path="dashboard-analytics")
    def dashboard_analytics(self, request, pk=None):
        influencer = self.get_object()
        
        # Período de 30 dias
        periodo = timezone.now() - timedelta(days=30)

        # Métricas de cliques
        cliques_mes = Click.objects.filter(influencer=influencer, timestamp__gte=periodo).count()
        
        produto_mais_clicado = Produto.objects.filter(
            influencer=influencer, cliques__timestamp__gte=periodo
        ).annotate(
            num_cliques=Count('cliques')
        ).order_by('-num_cliques').first()

        loja_mais_clicada = LojaParceira.objects.filter(
            influencer=influencer, cliques__timestamp__gte=periodo
        ).annotate(
            num_cliques=Count('cliques')
        ).order_by('-num_cliques').first()

        produto_data = ProdutoSerializer(produto_mais_clicado, context={'request': request}).data if produto_mais_clicado else None
        if produto_data:
            produto_data['num_cliques'] = produto_mais_clicado.num_cliques

        loja_data = LojaParceiraSerializer(loja_mais_clicada, context={'request': request}).data if loja_mais_clicada else None
        if loja_data:
            loja_data['num_cliques'] = loja_mais_clicada.num_cliques

        return Response({
            "cliques_no_mes": cliques_mes,
            "produto_mais_clicado": produto_data,
            "loja_mais_clicada": loja_data,
        })


class LojaViewSet(viewsets.ModelViewSet):
    serializer_class = LojaSerializer
    permission_classes = [BasePermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["status", "categoria"]
    search_fields = ["nome", "slug"]
    ordering = ["-data_cadastro"]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Loja.objects.all()
        return Loja.objects.filter(influencer__usuario=user)

    def get_serializer_context(self):
        context = super(LojaViewSet, self).get_serializer_context()
        context.update({"request": self.request})
        return context

    @action(detail=False, methods=['post'], url_path='verificar-slug')
    def verificar_slug(self, request):
        slug = request.data.get('slug')
        if not slug:
            return Response({'error': 'Slug não fornecido.'}, status=status.HTTP_400_BAD_REQUEST)
        
        exists = Loja.objects.filter(slug=slug).exists()
        return Response({'disponivel': not exists})


class ProdutoViewSet(viewsets.ModelViewSet):
    serializer_class = ProdutoSerializer
    permission_classes = [BasePermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["status", "categoria", "loja"]
    search_fields = ["nome", "descricao"]
    ordering = ["-data_cadastro"]

    def get_serializer_context(self):
        context = super(ProdutoViewSet, self).get_serializer_context()
        context.update({"request": self.request})
        return context

    def get_queryset(self):
        user = self.request.user
        qs = Produto.objects.all() if user.is_staff else Produto.objects.filter(influencer__usuario=user)
        loja_id = self.request.query_params.get("loja")
        if loja_id:
            qs = qs.filter(loja_id=loja_id)
        return qs


class LojaParceiraViewSet(viewsets.ModelViewSet):
    serializer_class = LojaParceiraSerializer
    permission_classes = [BasePermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["status", "categoria"]
    search_fields = ["nome", "url"]
    ordering = ["-data_cadastro"]

    def get_serializer_context(self):
        context = super(LojaParceiraViewSet, self).get_serializer_context()
        context.update({"request": self.request})
        return context

    def get_queryset(self):
        from .models import LojaParceira
        user = self.request.user
        if user.is_staff:
            return LojaParceira.objects.all()
        return LojaParceira.objects.filter(influencer__usuario=user)

    def perform_create(self, serializer):
        # Vincula automaticamente ao influencer do usuário
        influencer = Influencer.objects.filter(usuario=self.request.user).first()
        serializer.save(influencer=influencer)


class VendaViewSet(viewsets.ModelViewSet):
    serializer_class = VendaSerializer
    permission_classes = [BasePermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["status", "origem", "produto"]
    search_fields = ["cliente_nome", "cliente_email", "produto__nome"]
    ordering = ["-data_venda"]

    def get_queryset(self):
        user = self.request.user
        return Venda.objects.all() if user.is_staff else Venda.objects.filter(influencer__usuario=user)

    @action(detail=False, methods=["get"], url_path="relatorio")
    def relatorio(self, request):
        user = request.user
        qs = Venda.objects.all() if user.is_staff else Venda.objects.filter(influencer__usuario=user)
        agg = qs.aggregate(total=Sum("preco_total"), qtd=Sum("quantidade"), com=Sum("comissao"))
        total_vendas = agg.get('total') or 0
        total_quantidade = agg.get('qtd') or 0
        total_comissao = agg.get('com') or 0
        return Response({
            "total_vendas": total_vendas,
            "total_quantidade": total_quantidade,
            "total_comissao": total_comissao,
        })


## FaturaViewSet removido


class PostViewSet(viewsets.ModelViewSet):
    serializer_class = PostSerializer
    permission_classes = [BasePermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["status", "plataforma", "produto"]
    search_fields = ["conteudo"]
    ordering = ["-data_geracao"]

    def get_queryset(self):
        user = self.request.user
        return Post.objects.all() if user.is_staff else Post.objects.filter(influencer__usuario=user)

    @action(detail=False, methods=["post"], url_path="gerar")
    def gerar(self, request):
        influencer_id = request.data.get("influencer")
        produto_id = request.data.get("produto")
        plataforma = request.data.get("plataforma", "instagram")
        conteudo = request.data.get("conteudo")
        if not conteudo:
            conteudo = f"Post automático para plataforma {plataforma}."
        post = Post.objects.create(
            influencer_id=influencer_id or getattr(getattr(request.user, 'influencer', None), 'id', None),
            produto_id=produto_id,
            plataforma=plataforma,
            conteudo=conteudo,
        )
        serializer = self.get_serializer(post)
        return Response(serializer.data)


class ClickViewSet(viewsets.ModelViewSet):
    queryset = Click.objects.all()
    serializer_class = ClickSerializer
    permission_classes = [permissions.AllowAny]  # Permite que qualquer pessoa (mesmo não logada) registre o clique

    def get_queryset(self):
        # Admin/staff podem ver todos os cliques. Usuário logado pode ver apenas os seus.
        user = self.request.user
        if user.is_authenticated:
            if user.is_staff:
                return Click.objects.all()
            return Click.objects.filter(influencer__usuario=user)
        return Click.objects.none()  # Não mostrar cliques para usuários não autenticados via GET

    def create(self, request, *args, **kwargs):
        produto_id = request.data.get('produto')
        loja_id = request.data.get('loja_parceira')
        tipo_clique = request.data.get('tipo_clique')
        influencer_id = request.data.get('influencer')

        produto = Produto.objects.filter(pk=produto_id).first() if produto_id else None
        loja = LojaParceira.objects.filter(pk=loja_id).first() if loja_id else None

        influencer = None
        if influencer_id:
            influencer = Influencer.objects.filter(pk=influencer_id).first()
        if influencer is None:
            if produto is not None:
                influencer = produto.influencer
            elif loja is not None:
                influencer = loja.influencer

        if influencer is None:
            return Response({"detail": "Influencer não encontrado."}, status=status.HTTP_400_BAD_REQUEST)

        # Ajusta tipo_clique se vier inválido
        valid_tipos = dict(Click.TIPO_CHOICES).keys()
        if tipo_clique not in valid_tipos:
            tipo_clique = 'produto_comprar' if produto else 'loja_destaque'

        click = Click.objects.create(
            influencer=influencer,
            produto=produto,
            loja_parceira=loja,
            tipo_clique=tipo_clique,
        )
        serializer = ClickSerializer(click, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class VisitaInfluencerViewSet(viewsets.ModelViewSet):
    """ViewSet para gerenciar visitas de influencer"""
    queryset = VisitaInfluencer.objects.all()
    serializer_class = VisitaInfluencerSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    @action(detail=False, methods=['post'], url_path='registrar')
    def registrar_visita(self, request):
        """Registra uma nova visita para o influencer logado"""
        try:
            # Obtém o influencer do usuário logado
            influencer = Influencer.objects.get(usuario=request.user)
            
            # Obtém informações da requisição
            ip_address = self._get_client_ip(request)
            user_agent = request.META.get('HTTP_USER_AGENT', '')
            referer = request.META.get('HTTP_REFERER', '')
            
            # Detecta o tipo de dispositivo
            device_type = self._detect_device_type(user_agent)
            
            # Cria a visita
            visita = VisitaInfluencer.objects.create(
                influencer=influencer,
                ip_address=ip_address,
                user_agent=user_agent,
                referer=referer,
                device_type=device_type,
                session_id=request.session.session_key or None
            )
            
            serializer = self.get_serializer(visita)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except Influencer.DoesNotExist:
            return Response(
                {'error': 'Influencer não encontrado para este usuário'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': f'Erro ao registrar visita: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _get_client_ip(self, request):
        """Obtém o IP real do cliente"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def _detect_device_type(self, user_agent):
        """Detecta o tipo de dispositivo baseado no user agent"""
        user_agent_lower = user_agent.lower()
        
        if any(mobile in user_agent_lower for mobile in ['mobile', 'android', 'iphone', 'ipad']):
            return 'mobile'
        elif 'tablet' in user_agent_lower:
            return 'tablet'
        else:
            return 'desktop'

