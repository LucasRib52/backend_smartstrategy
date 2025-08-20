from rest_framework import serializers
from .models import Categoria, Influencer, Loja, LojaParceira, Produto, Venda, Post, Click, VisitaInfluencer
from django.utils.crypto import get_random_string
import json


class CategoriaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Categoria
        fields = [
            "id",
            "nome",
            "descricao",
            "icone",
            "cor",
            "status",
        ]


class InfluencerSerializer(serializers.ModelSerializer):
    categorias_secundarias = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Categoria.objects.all(), required=False
    )

    class Meta:
        model = Influencer
        fields = [
            "id",
            "usuario",
            "nome_artistico",
            "biografia",
            "redes_sociais",
            "categoria_principal",
            "categorias_secundarias",
            "data_cadastro",
            "status",
            "comissao_padrao",
        ]
        read_only_fields = ["data_cadastro"]


class LojaSerializer(serializers.ModelSerializer):
    logo_layout_url = serializers.SerializerMethodField()
    banner_layout_url = serializers.SerializerMethodField()

    class Meta:
        model = Loja
        fields = [
            "id",
            "influencer",
            "nome",
            "slug",
            "categoria",
            "comissao",
            "status",
            "data_cadastro",
            "configuracoes",
            "layout_escolhido",
            "logo_layout",
            "banner_layout",
            "logo_layout_url",
            "banner_layout_url",
        ]
        read_only_fields = ["data_cadastro", "slug"]

    def get_logo_layout_url(self, obj):
        request = self.context.get("request")
        if getattr(obj, "logo_layout", None):
            url = obj.logo_layout.url
            return request.build_absolute_uri(url) if request else url
        return None

    def get_banner_layout_url(self, obj):
        request = self.context.get("request")
        if getattr(obj, "banner_layout", None):
            url = obj.banner_layout.url
            return request.build_absolute_uri(url) if request else url
        return None

    def validate_configuracoes(self, value):
        # Aceita string JSON quando vier via multipart
        if isinstance(value, str):
            try:
                return json.loads(value)
            except Exception:
                return {}
        return value


class LojaParceiraSerializer(serializers.ModelSerializer):
    categoria_nome = serializers.SerializerMethodField()
    logo_url_display = serializers.SerializerMethodField()
    
    class Meta:
        model = LojaParceira
        fields = [
            "id",
            "influencer",
            "nome",
            "url",
            "logo",
            "logo_url",
            "logo_url_display",
            "categoria",
            "categoria_nome",
            "comissao",
            "status",
            "data_cadastro",
        ]
        read_only_fields = ["data_cadastro", "influencer"]

    def get_logo_url_display(self, obj):
        request = self.context.get("request")
        if obj.logo and hasattr(obj.logo, 'url'):
            return request.build_absolute_uri(obj.logo.url)
        if obj.logo_url:
            return obj.logo_url
        return None

    def get_categoria_nome(self, obj):
        try:
            return obj.categoria.nome if obj.categoria else None
        except Exception:
            return None


class ProdutoSerializer(serializers.ModelSerializer):
    categoria_nome = serializers.SerializerMethodField()
    loja_nome = serializers.SerializerMethodField()
    loja_logo_url = serializers.SerializerMethodField()
    loja_comissao = serializers.SerializerMethodField()
    imagem_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Produto
        fields = [
            "id",
            "influencer",
            "loja",  # agora LojaParceira
            "nome",
            "descricao",
            "preco",
            "categoria",
            "link_afiliado",
            "imagem",
            "imagem_url",
            "status",
            "data_cadastro",
            "metadados",
            "categoria_nome",
            "loja_nome",
            "loja_logo_url",
            "loja_comissao",
        ]
        read_only_fields = ["data_cadastro"]

    def validate_imagem(self, value):
        # Permitir None ou valores vazios durante atualizações
        if value is None or value == '':
            return None
        return value

    def validate_preco(self, value):
        if value is None or value <= 0:
            raise serializers.ValidationError("Preço deve ser maior que zero.")
        return value

    def validate_loja(self, value):
        if value == '':
            return None
        return value

    def validate_categoria(self, value):
        if value == '':
            return None
        return value

    def validate_link_afiliado(self, value):
        if value == '':
            return None
        return value



    def validate(self, attrs):
        influencer = attrs.get("influencer") or getattr(self.instance, "influencer", None)
        loja = attrs.get("loja") or getattr(self.instance, "loja", None)
        if loja is None:
            if self.instance is None or ('loja' in attrs and attrs.get('loja') != getattr(self.instance, "loja", None)):
                raise serializers.ValidationError({"loja": "Loja é obrigatória."})
        if influencer and loja and getattr(loja, "influencer_id", None) != getattr(influencer, "id", None):
            raise serializers.ValidationError({"loja": "Loja deve pertencer ao mesmo influencer."})
        return attrs

    def get_categoria_nome(self, obj):
        try:
            return obj.categoria.nome if obj.categoria else None
        except Exception:
            return None

    def get_loja_nome(self, obj):
        try:
            return obj.loja.nome if obj.loja else None
        except Exception:
            return None

    def get_loja_logo_url(self, obj):
        try:
            return obj.loja.logo_url if obj.loja else None
        except Exception:
            return None

    def get_loja_comissao(self, obj):
        try:
            return float(obj.loja.comissao) if obj.loja and obj.loja.comissao else None
        except Exception:
            return None

    def get_imagem_url(self, obj):
        try:
            if obj.imagem:
                url = obj.imagem.url
                request = self.context.get("request")
                return request.build_absolute_uri(url) if request else url
            return None
        except Exception:
            return None

    def _ensure_affiliate_link(self, produto: Produto) -> str:
        if produto.link_afiliado:
            return produto.link_afiliado
        ref = produto.influencer.usuario_id if produto.influencer_id else get_random_string(8)
        return f"https://go.influstore.com/p/{produto.id}?ref={ref}"

    def create(self, validated_data):
        produto = Produto.objects.create(**validated_data)
        # Se imagem não vier, deixa None (não obrigatório)
        if not produto.link_afiliado:
            produto.link_afiliado = self._ensure_affiliate_link(produto)
            produto.save(update_fields=["link_afiliado"])
        return produto

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if not instance.link_afiliado:
            instance.link_afiliado = self._ensure_affiliate_link(instance)
            instance.save(update_fields=["link_afiliado"])
        return instance


class VendaSerializer(serializers.ModelSerializer):
    produto_nome = serializers.SerializerMethodField()
    loja_nome = serializers.SerializerMethodField()
    loja_id = serializers.SerializerMethodField()
    
    class Meta:
        model = Venda
        fields = [
            "id",
            "influencer",
            "produto",
            "produto_nome",
            "loja_id",
            "loja_nome",
            "cliente_nome",
            "cliente_email",
            "quantidade",
            "preco_unitario",
            "preco_total",
            "comissao",
            "data_venda",
            "status",
            "origem",
        ]
        read_only_fields = ["preco_total", "comissao"]

    def get_produto_nome(self, obj):
        try:
            return obj.produto.nome if obj.produto else None
        except Exception:
            return None
    
    def get_loja_nome(self, obj):
        try:
            return obj.produto.loja.nome if obj.produto and obj.produto.loja else None
        except Exception:
            return None
    
    def get_loja_id(self, obj):
        try:
            return obj.produto.loja.id if obj.produto and obj.produto.loja else None
        except Exception:
            return None

    def validate_quantidade(self, value):
        if value is None or value <= 0:
            raise serializers.ValidationError("Quantidade deve ser maior que zero.")
        return value


## Faturas removidas do módulo influencer


class PostSerializer(serializers.ModelSerializer):
    class Meta:
        model = Post
        fields = [
            "id",
            "influencer",
            "produto",
            "plataforma",
            "conteudo",
            "data_geracao",
            "data_publicacao",
            "status",
            "metricas",
        ]
        read_only_fields = ["data_geracao"]


class ClickSerializer(serializers.ModelSerializer):
    class Meta:
        model = Click
        fields = [
            'id',
            'influencer',
            'produto',
            'loja_parceira',
            'timestamp',
            'tipo_clique'
        ]
        read_only_fields = ['id', 'timestamp']
        extra_kwargs = {
            'influencer': {'required': False},
            'produto': {'required': False, 'allow_null': True},
            'loja_parceira': {'required': False, 'allow_null': True},
        }

    def validate(self, data):
        if not data.get('influencer') and not data.get('produto') and not data.get('loja_parceira'):
            raise serializers.ValidationError("É necessário associar pelo menos um influencer, produto ou loja parceira.")
        return data

    def create(self, validated_data):
        produto = validated_data.get('produto')
        loja = validated_data.get('loja_parceira')
        
        if 'influencer' not in validated_data:
            if produto:
                validated_data['influencer'] = produto.influencer
            elif loja:
                validated_data['influencer'] = loja.influencer
            else:
                raise serializers.ValidationError("Não foi possível determinar o influencer.")
            
        return Click.objects.create(**validated_data)


class VisitaInfluencerSerializer(serializers.ModelSerializer):
    """Serializer para o modelo VisitaInfluencer"""
    
    class Meta:
        model = VisitaInfluencer
        fields = [
            'id', 'influencer', 'ip_address', 'user_agent', 'referer',
            'country', 'city', 'region', 'data_visita', 'data_visita_date',
            'session_id', 'device_type'
        ]
        read_only_fields = ['id', 'data_visita', 'data_visita_date']


