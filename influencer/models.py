from django.db import models
from django.conf import settings
import uuid
from decimal import Decimal
from django.utils.text import slugify
from django.utils import timezone


class Categoria(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome = models.CharField(max_length=120, unique=True)
    descricao = models.TextField(blank=True, null=True)
    icone = models.CharField(max_length=120, blank=True, null=True)
    cor = models.CharField(max_length=32, blank=True, null=True)
    criador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="categorias_criadas",
    )
    status = models.CharField(
        max_length=16,
        choices=(
            ("ativo", "Ativo"),
            ("inativo", "Inativo"),
        ),
        default="ativo",
    )

    class Meta:
        verbose_name = "Categoria"
        verbose_name_plural = "Categorias"

    def __str__(self) -> str:
        return self.nome


class Influencer(models.Model):
    STATUS_CHOICES = (
        ("ativo", "Ativo"),
        ("inativo", "Inativo"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="influencers",
    )
    nome_artistico = models.CharField(max_length=150, blank=True, null=True)
    biografia = models.TextField(blank=True, null=True)
    redes_sociais = models.JSONField(default=dict, blank=True)
    categoria_principal = models.ForeignKey(
        Categoria, on_delete=models.SET_NULL, null=True, blank=True, related_name="influencers_principais"
    )
    categorias_secundarias = models.ManyToManyField(
        Categoria, blank=True, related_name="influencers_secundarios"
    )
    data_cadastro = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="ativo")
    comissao_padrao = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("10.00"))

    class Meta:
        verbose_name = "Influencer"
        verbose_name_plural = "Influencers"
        indexes = [
            models.Index(fields=["usuario"]),
        ]

    def __str__(self) -> str:
        return self.nome_artistico or f"Influencer {self.usuario_id}"


class Loja(models.Model):
    STATUS_CHOICES = (
        ("ativo", "Ativo"),
        ("inativo", "Inativo"),
    )
    LAYOUT_CHOICES = (
        (1, "Layout 1"),
        (2, "Layout 2"),
        (3, "Layout 3"),
        (4, "Layout 4"),
        (5, "Layout 5"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    influencer = models.ForeignKey(Influencer, on_delete=models.CASCADE, related_name="lojas")
    nome = models.CharField(max_length=150)
    slug = models.SlugField(max_length=100, unique=True, blank=True, help_text="O nome que aparecerá na URL, ex: seudominio.com/nome-da-loja")
    categoria = models.ForeignKey(Categoria, on_delete=models.SET_NULL, null=True, blank=True, related_name="lojas")
    comissao = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="ativo")
    data_cadastro = models.DateTimeField(auto_now_add=True)
    configuracoes = models.JSONField(default=dict, blank=True)
    layout_escolhido = models.IntegerField(choices=LAYOUT_CHOICES, default=1)
    # Novos campos para imagens do layout (upload em media/influencer/layout/...)
    logo_layout = models.ImageField(upload_to='influencer/layout/logos/', blank=True, null=True)
    banner_layout = models.ImageField(upload_to='influencer/layout/banners/', blank=True, null=True)

    class Meta:
        verbose_name = "Loja"
        verbose_name_plural = "Lojas"
        constraints = [
            models.UniqueConstraint(fields=["influencer", "nome"], name="unique_loja_por_influencer_nome"),
        ]

    def __str__(self) -> str:
        return f"{self.nome} ({self.slug})"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nome)
        
        original_slug = self.slug
        queryset = Loja.objects.filter(slug__startswith=original_slug).exclude(id=self.id)
        counter = 1
        while queryset.filter(slug=self.slug).exists():
            self.slug = f'{original_slug}-{counter}'
            counter += 1
            
        super().save(*args, **kwargs)


class LojaParceira(models.Model):
    STATUS_CHOICES = (
        ("ativo", "Ativo"),
        ("inativo", "Inativo"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    influencer = models.ForeignKey(Influencer, on_delete=models.CASCADE, related_name="lojas_parceiras")
    nome = models.CharField(max_length=150)
    url = models.URLField(max_length=500)
    logo = models.ImageField(upload_to='influencer/logoloja/', blank=True, null=True)
    logo_url = models.URLField(max_length=500, blank=True, null=True)
    categoria = models.ForeignKey(Categoria, on_delete=models.SET_NULL, null=True, blank=True, related_name="lojas_parceiras")
    comissao = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="ativo")
    data_cadastro = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Loja Parceira"
        verbose_name_plural = "Lojas Parceiras"
        ordering = ["-data_cadastro"]

    @property
    def get_logo_url(self):
        if self.logo:
            return self.logo.url
        return self.logo_url

    def __str__(self) -> str:
        return f"{self.nome}"

class Produto(models.Model):
    STATUS_CHOICES = (
        ("ativo", "Ativo"),
        ("inativo", "Inativo"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    influencer = models.ForeignKey(Influencer, on_delete=models.CASCADE, related_name="produtos")
    loja = models.ForeignKey('LojaParceira', on_delete=models.SET_NULL, null=True, blank=True, related_name="produtos")
    nome = models.CharField(max_length=200)
    descricao = models.TextField(blank=True, null=True)
    preco = models.DecimalField(max_digits=10, decimal_places=2)
    categoria = models.ForeignKey(Categoria, on_delete=models.SET_NULL, null=True, blank=True, related_name="produtos")
    link_afiliado = models.URLField(max_length=500, blank=True, null=True)
    imagem = models.ImageField(upload_to='influencer/produtos/', blank=True, null=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="ativo")
    data_cadastro = models.DateTimeField(auto_now_add=True)
    metadados = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "Produto"
        verbose_name_plural = "Produtos"
        indexes = [
            models.Index(fields=["nome"]),
        ]

    @property
    def imagem_url(self):
        """Retorna a URL da imagem uploadada"""
        if self.imagem:
            return self.imagem.url
        return None

    def __str__(self) -> str:
        return self.nome


class Venda(models.Model):
    STATUS_CHOICES = (
        ("pendente", "Pendente"),
        ("confirmada", "Confirmada"),
        ("cancelada", "Cancelada"),
    )
    ORIGEM_CHOICES = (
        ("manual", "Manual"),
        ("api", "API"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    influencer = models.ForeignKey(Influencer, on_delete=models.CASCADE, related_name="vendas")
    produto = models.ForeignKey(Produto, on_delete=models.PROTECT, related_name="vendas")
    cliente_nome = models.CharField(max_length=150)
    cliente_email = models.EmailField()
    quantidade = models.PositiveIntegerField(default=1)
    preco_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    preco_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    comissao = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    data_venda = models.DateTimeField()
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="pendente")
    origem = models.CharField(max_length=16, choices=ORIGEM_CHOICES, default="manual")

    class Meta:
        verbose_name = "Venda"
        verbose_name_plural = "Vendas"
        indexes = [
            models.Index(fields=["data_venda"]),
        ]

    def __str__(self) -> str:
        return f"Venda {self.id} - {self.produto.nome}"

    def calcular_comissao_percentual(self) -> Decimal:
        if self.produto and self.produto.loja and self.produto.loja.comissao is not None:
            return Decimal(self.produto.loja.comissao)
        if self.influencer and self.influencer.comissao_padrao is not None:
            return Decimal(self.influencer.comissao_padrao)
        return Decimal("0.00")

    def save(self, *args, **kwargs):
        self.preco_total = (self.preco_unitario or Decimal("0.00")) * Decimal(self.quantidade or 0)
        percentual = self.calcular_comissao_percentual()  # 0-100
        self.comissao = (self.preco_total * percentual) / Decimal("100.00")
        super().save(*args, **kwargs)


## Faturas removidas do módulo influencer


class Post(models.Model):
    STATUS_CHOICES = (
        ("rascunho", "Rascunho"),
        ("publicado", "Publicado"),
    )
    PLATAFORMA_CHOICES = (
        ("instagram", "Instagram"),
        ("facebook", "Facebook"),
        ("tiktok", "TikTok"),
        ("twitter", "Twitter"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    influencer = models.ForeignKey(Influencer, on_delete=models.CASCADE, related_name="posts")
    produto = models.ForeignKey(Produto, on_delete=models.SET_NULL, null=True, blank=True, related_name="posts")
    plataforma = models.CharField(max_length=16, choices=PLATAFORMA_CHOICES)
    conteudo = models.TextField()
    data_geracao = models.DateTimeField(auto_now_add=True)
    data_publicacao = models.DateTimeField(blank=True, null=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="rascunho")
    metricas = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "Post"
        verbose_name_plural = "Posts"
        ordering = ["-data_geracao"]

    def __str__(self) -> str:
        return f"Post {self.id} - {self.plataforma}"


class Click(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    influencer = models.ForeignKey(Influencer, on_delete=models.CASCADE, related_name="cliques")
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE, null=True, blank=True, related_name="cliques")
    loja_parceira = models.ForeignKey(LojaParceira, on_delete=models.CASCADE, null=True, blank=True, related_name="cliques")
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    TIPO_CHOICES = (
        ("produto_comprar", "Clique Comprar Agora (Produto)"),
        ("loja_destaque", "Clique em Loja (Destaque)"),
    )
    tipo_clique = models.CharField(max_length=50, choices=TIPO_CHOICES)

    class Meta:
        verbose_name = "Clique"
        verbose_name_plural = "Cliques"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["produto"]),
            models.Index(fields=["loja_parceira"]),
        ]

    def __str__(self):
        if self.produto:
            return f"Clique no produto {self.produto.nome} em {self.timestamp}"
        if self.loja_parceira:
            return f"Clique na loja {self.loja_parceira.nome} em {self.timestamp}"
        return f"Clique genérico em {self.timestamp}"


class VisitaInfluencer(models.Model):
    """Modelo para rastrear visitas ao dashboard de influencer"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    influencer = models.ForeignKey(Influencer, on_delete=models.CASCADE, related_name="visitas")
    
    # Informações da visita
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)
    referer = models.URLField(blank=True, null=True)
    
    # Dados de localização (se disponível)
    country = models.CharField(max_length=100, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    region = models.CharField(max_length=100, blank=True, null=True)
    
    # Timestamps
    data_visita = models.DateTimeField(auto_now_add=True)
    data_visita_date = models.DateField(auto_now_add=True)  # Para agregações por data
    
    # Metadados adicionais
    session_id = models.CharField(max_length=255, blank=True, null=True)
    device_type = models.CharField(max_length=50, blank=True, null=True)  # mobile, desktop, tablet
    
    class Meta:
        verbose_name = "Visita de Influencer"
        verbose_name_plural = "Visitas de Influencer"
        ordering = ['-data_visita']
        indexes = [
            models.Index(fields=['influencer', 'data_visita']),
            models.Index(fields=['data_visita_date']),
            models.Index(fields=['influencer', 'data_visita_date']),
        ]
    
    def __str__(self):
        return f"Visita de {self.influencer.nome_artistico} em {self.data_visita.strftime('%d/%m/%Y %H:%M')}"
    
    def save(self, *args, **kwargs):
        # Garantir que data_visita_date seja sempre preenchida
        if not self.data_visita_date:
            from datetime import date
            self.data_visita_date = date.today()
        super().save(*args, **kwargs)

# Create your models here.
