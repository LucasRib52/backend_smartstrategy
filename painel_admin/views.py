from django.shortcuts import render
from rest_framework import viewsets, views, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db import models
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from django.contrib.auth import get_user_model
import locale

from empresas.models import Empresa, Responsavel
from empresas.serializers import ResponsavelSerializer
from assinaturas.models import Assinatura, Plano, HistoricoPagamento
from .serializers import EmpresaAdminSerializer, PFUserAdminSerializer, AssinaturaAdminSerializer, PlanoAdminSerializer, PFUserAdminWriteSerializer, HistoricoPagamentoSerializer, NotificacaoAdminSerializer
from .models import NotificacaoAdmin
from .notificacoes_utils import (
    criar_notificacao_empresa_bloqueada,
    criar_notificacao_empresa_ativada,
    criar_notificacao_assinatura_criada,
    criar_notificacao_plano_expirado,
    criar_notificacao_plano_renovado,
    criar_notificacao_pagamento_recebido,
    criar_notificacao_usuario_criado
)


def registrar_historico_pagamento(assinatura, tipo, descricao, request=None, **kwargs):
    """Função helper para registrar mudanças no histórico de pagamentos."""
    try:
        HistoricoPagamento.objects.create(
            assinatura=assinatura,
            tipo=tipo,
            descricao=descricao,
            usuario_admin=request.user if request else None,
            **kwargs
        )
    except Exception as e:
        print(f"Erro ao registrar histórico: {e}")


class AdminDashboardAPIView(views.APIView):
    """Endpoint completo do dashboard admin com filtros e dados em tempo real."""

    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        # Parâmetros de filtro
        period = request.query_params.get('period', '30d')
        status_filter = request.query_params.get('status', 'all')
        type_filter = request.query_params.get('type', 'all')
        
        # Calcular período baseado no filtro
        hoje = timezone.now()
        if period == '7d':
            inicio_periodo = hoje - relativedelta(days=7)
        elif period == '30d':
            inicio_periodo = hoje - relativedelta(days=30)
        elif period == '90d':
            inicio_periodo = hoje - relativedelta(days=90)
        elif period == '1y':
            inicio_periodo = hoje - relativedelta(years=1)
        else:
            inicio_periodo = hoje - relativedelta(days=30)  # padrão 30 dias

        from django.db.models import OuterRef, Subquery, BooleanField, ExpressionWrapper, Q
        
        # Base queryset: todas empresas
        empresas_base = Empresa.objects.all().only('id', 'nome_fantasia', 'sigla', 'created_at', 'tipo', 'ativo')
        assinatura_mais_recente = Assinatura.objects.filter(
            empresa=OuterRef('pk')
        ).order_by('-inicio')
        
        # Anotar se a assinatura mais recente está expirada e o fim dela
        empresas_base = empresas_base.annotate(
            assinatura_expirada=Subquery(assinatura_mais_recente.values('expirada')[:1]),
            assinatura_fim=Subquery(assinatura_mais_recente.values('fim')[:1]),
            assinatura_ativa=Subquery(assinatura_mais_recente.values('ativa')[:1]),
            assinatura_plano_codigo=Subquery(assinatura_mais_recente.values('plano__codigo')[:1]),
        )
        
        # Filtro de período: assinatura mais recente expirada dentro do período
        if status_filter == 'expired':
            empresas_qs = empresas_base.filter(
                assinatura_expirada=True,
                assinatura_fim__gte=inicio_periodo
            )
        elif status_filter == 'active':
            empresas_qs = empresas_base.filter(
                assinatura_ativa=True,
                assinatura_expirada=False
            ).exclude(assinatura_plano_codigo='TRIAL')
        elif status_filter == 'trial':
            empresas_qs = empresas_base.filter(
                assinatura_plano_codigo='TRIAL',
                assinatura_ativa=True,
                assinatura_expirada=False
            )
        else:
            empresas_qs = empresas_base
        
        # Filtro de tipo
        if type_filter == 'pj':
            empresas_qs = empresas_qs.filter(tipo='PJ')
        elif type_filter == 'pf':
            empresas_qs = empresas_qs.filter(tipo='PF')
        
        # Filtro de período para empresas criadas (exceto expiradas)
        if status_filter != 'expired':
            empresas_qs = empresas_qs.filter(created_at__gte=inicio_periodo)
        
        # Métricas básicas
        total_empresas = empresas_qs.values('id').distinct().count()
        empresas_trial = empresas_qs.filter(
            assinatura_plano_codigo='TRIAL',
            assinatura_ativa=True,
            assinatura_expirada=False
        ).values('id').distinct().count()
        empresas_pagas = empresas_qs.filter(
            assinatura_ativa=True,
            assinatura_expirada=False
        ).exclude(assinatura_plano_codigo='TRIAL').values('id').distinct().count()
        empresas_expiradas = empresas_qs.filter(
            assinatura_expirada=True
        ).values('id').distinct().count()
        empresas_ativas_total = empresas_qs.filter(ativo=True).values('id').distinct().count()

        # MRR (Monthly Recurring Revenue) otimizado
        from django.db.models import Sum, F
        mrr_total = Assinatura.objects.filter(
            inicio__gte=inicio_periodo
        ).only('id').aggregate(total=Sum(F('plano__preco')))['total'] or 0

        # Calcular conversão (empresas pagas / total empresas)
        conversao = 0
        if total_empresas > 0:
            conversao = round((empresas_pagas / total_empresas) * 100, 1)

        # Gráfico de crescimento de empresas: últimos 12 meses
        locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')
        empresas_por_mes = []
        for i in range(11, -1, -1):
            mes_referencia = hoje - relativedelta(months=i)
            mes_inicio = mes_referencia.replace(day=1)
            mes_fim = (mes_inicio + relativedelta(months=1)) - relativedelta(days=1)
            
            # Aplicar filtros de período se necessário
            if status_filter != 'expired':
                empresas_mes = Empresa.objects.filter(
                    created_at__date__gte=mes_inicio,
                    created_at__date__lte=mes_fim
                )
            else:
                # Para empresas expiradas, incluir todas que expiraram no mês
                empresas_mes = Empresa.objects.filter(
                    models.Q(created_at__date__gte=mes_inicio, created_at__date__lte=mes_fim) |
                    models.Q(assinaturas__expirada=True, assinaturas__fim__date__gte=mes_inicio, assinaturas__fim__date__lte=mes_fim)
                )
            
            count = empresas_mes.count()
            ativas = empresas_mes.filter(ativo=True).count()
            expiradas = 0
            for empresa in empresas_mes:
                if not empresa.ativo:
                    expiradas += 1
                else:
                    assinatura_ativa = empresa.assinaturas.order_by('-inicio').first()
                    if assinatura_ativa and assinatura_ativa.expirada:
                        expiradas += 1
            empresas_por_mes.append({
                'month': mes_inicio.strftime('%b/%y').capitalize(),
                'count': count,
                'ativas': ativas,
                'expiradas': expiradas
            })

        # Receita mensal: últimos 12 meses, somando todos os pagamentos/renovações/criações de assinatura do mês
        receita_por_mes = []
        for i in range(11, -1, -1):
            mes_referencia = hoje - relativedelta(months=i)
            mes_inicio = mes_referencia.replace(day=1)
            mes_fim = (mes_inicio + relativedelta(months=1)) - relativedelta(days=1)
            pagamentos_qs = HistoricoPagamento.objects.filter(
                criado_em__date__gte=mes_inicio,
                criado_em__date__lte=mes_fim,
                tipo__in=['CRIACAO', 'EXTENSAO', 'REATIVACAO', 'TROCA_PLANO']
            )
            receita = pagamentos_qs.aggregate(total=Sum('valor_novo'))['total'] or 0
            novos = pagamentos_qs.count()
            # Contagem por plano
            planos_count = {}
            for plano in Plano.objects.all():
                planos_count[plano.nome] = pagamentos_qs.filter(assinatura__plano=plano).count()
            receita_por_mes.append({
                'month': mes_inicio.strftime('%b/%y').capitalize(),
                'revenue': float(receita),
                'novos': novos,
                'planos': planos_count
            })

        # Garantir que status_distribution sempre tenha as 3 chaves
        status_distribution = {
            'Trial': empresas_trial or 0,
            'Paga': empresas_pagas or 0,
            'Expirada': empresas_expiradas or 0
        }

        # Atividades recentes (empresas criadas + pagamentos/renovações)
        atividades_recentes = []
        # --- Empresas criadas recentemente ---
        empresas_ids = list(empresas_qs.values_list('id', flat=True).distinct()[:4])
        empresas_recentes = Empresa.objects.filter(id__in=empresas_ids).order_by('-created_at')
        for empresa in empresas_recentes:
            tempo_atras = hoje - empresa.created_at
            if tempo_atras.days == 0:
                if tempo_atras.seconds < 3600:
                    tempo_str = f"{max(tempo_atras.seconds // 60,1)} min"
                else:
                    tempo_str = f"{tempo_atras.seconds // 3600}h"
            elif tempo_atras.days == 1:
                tempo_str = "1 dia"
            else:
                tempo_str = f"{tempo_atras.days} dias"
            atividades_recentes.append({
                'type': 'empresa_criada',
                'title': 'Nova empresa cadastrada',
                'description': getattr(empresa, 'nome_fantasia', None) or getattr(empresa, 'sigla', ''),
                'time': tempo_str,
                'status': 'success',
                'timestamp': empresa.created_at
            })

        # --- Pagamentos / renovações recentes ---
        pagamentos_recentes = HistoricoPagamento.objects.filter(
            criado_em__gte=inicio_periodo,
            tipo__in=['CRIACAO', 'EXTENSAO', 'REATIVACAO', 'TROCA_PLANO']
        ).select_related('assinatura__empresa').order_by('-criado_em')[:4]

        for pag in pagamentos_recentes:
            tempo_atras = hoje - pag.criado_em
            if tempo_atras.days == 0:
                if tempo_atras.seconds < 3600:
                    tempo_str = f"{max(tempo_atras.seconds // 60,1)} min"
                else:
                    tempo_str = f"{tempo_atras.seconds // 3600}h"
            elif tempo_atras.days == 1:
                tempo_str = "1 dia"
            else:
                tempo_str = f"{tempo_atras.days} dias"
            empresa_nome = pag.assinatura.empresa.nome_fantasia or pag.assinatura.empresa.sigla
            atividades_recentes.append({
                'type': 'pagamento',
                'title': 'Pagamento / Renovação',
                'description': f"{empresa_nome} - {pag.assinatura.plano.nome}",
                'time': tempo_str,
                'status': 'primary',
                'timestamp': pag.criado_em
            })

        # Ordenar por data e limitar a 8 últimas atividades
        atividades_recentes = sorted(atividades_recentes, key=lambda x: x['timestamp'], reverse=True)[:8]
        # Remover chave timestamp antes de retornar
        for act in atividades_recentes:
            act.pop('timestamp', None)

        # Contagem de usuários PF otimizada
        User = get_user_model()
        empresas_pf_total = User.objects.filter(user_type='PF').only('id').count()

        data = {
            'metrics': {
                'empresas_total': total_empresas,
                'empresas_trial': empresas_trial,
                'empresas_pagas': empresas_pagas,
                'empresas_expiradas': empresas_expiradas,
                'empresas_pf_total': empresas_pf_total,
                'empresas_ativas_total': empresas_ativas_total,
                'mrr_total': float(mrr_total),
                'conversao': conversao
            },
            'charts': {
                'empresas_por_mes': empresas_por_mes,
                'status_distribution': status_distribution,
                'receita_por_mes': receita_por_mes
            },
            'activities': atividades_recentes,  # Limitar a 4 atividades reais
            'filters': {
                'period': period,
                'status': status_filter,
                'type': type_filter
            }
        }
        
        return Response(data)


class AdminMetricsAPIView(views.APIView):
    """Endpoint de métricas resumidas para o painel admin."""

    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        total_empresas = Empresa.objects.count()
        empresas_trial = Empresa.objects.filter(
            assinaturas__ativa=True,
            assinaturas__expirada=False,
            assinaturas__plano__codigo='TRIAL'
        ).distinct().count()
        empresas_pagas = Empresa.objects.filter(
            assinaturas__ativa=True,
            assinaturas__expirada=False
        ).exclude(assinaturas__plano__codigo='TRIAL').distinct().count()
        empresas_expiradas = Empresa.objects.filter(
            assinaturas__expirada=True
        ).exclude(
            assinaturas__ativa=True, assinaturas__expirada=False
        ).distinct().count()
        empresas_pf_total = Empresa.objects.filter(tipo='PF').count()

        empresas_ativas_total = Empresa.objects.filter(ativo=True).count()

        from django.db.models import Sum, F  # local import to evitar conflitos circulares
        mrr_total = Assinatura.objects.filter(ativa=True, expirada=False).aggregate(total=Sum(F('plano__preco')))['total'] or 0

        data = {
            'empresas_total': total_empresas,
            'empresas_trial': empresas_trial,
            'empresas_pagas': empresas_pagas,
            'empresas_expiradas': empresas_expiradas,
            'empresas_pf_total': empresas_pf_total,
            'empresas_ativas_total': empresas_ativas_total,
            'mrr_total': float(mrr_total),
        }
        return Response(data)


class EmpresaAdminViewSet(viewsets.ModelViewSet):
    """CRUD e ações sobre empresas para admins."""
    queryset = Empresa.objects.all()
    serializer_class = EmpresaAdminSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    pagination_class = None

    def get_queryset(self):
        qs = super().get_queryset()
        situacao = self.request.query_params.get('situacao')

        from assinaturas.models import Assinatura
        from django.db.models import OuterRef, Subquery

        assinatura_mais_recente = Assinatura.objects.filter(
            empresa=OuterRef('pk')
        ).order_by('-inicio')

        if situacao == 'expirada':
            qs = qs.annotate(
                assinatura_expirada=Subquery(assinatura_mais_recente.values('expirada')[:1])
            ).filter(assinatura_expirada=True)
            empresa_ids = list(qs.values_list('id', flat=True))
            qs = Empresa.objects.filter(id__in=empresa_ids)
        elif situacao == 'ativa':
            qs = qs.annotate(
                assinatura_expirada=Subquery(assinatura_mais_recente.values('expirada')[:1]),
                assinatura_ativa=Subquery(assinatura_mais_recente.values('ativa')[:1])
            ).filter(ativo=True, assinatura_ativa=True, assinatura_expirada=False)
            empresa_ids = list(qs.values_list('id', flat=True))
            qs = Empresa.objects.filter(id__in=empresa_ids)
        elif situacao == 'bloqueada':
            qs = qs.filter(ativo=False)

        plano = self.request.query_params.get('plano')
        if plano == 'TRIAL':
            qs = qs.filter(assinaturas__plano__codigo='TRIAL', assinaturas__ativa=True, assinaturas__expirada=False)
        elif plano == 'PAGO':
            qs = qs.exclude(assinaturas__plano__codigo='TRIAL').filter(assinaturas__ativa=True, assinaturas__expirada=False)
        elif plano == 'EXPIRADA':
            qs = qs.filter(assinaturas__expirada=True)

        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(models.Q(nome_fantasia__icontains=search) | models.Q(sigla__icontains=search) | models.Q(email_comercial__icontains=search))
        return qs.distinct()

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['tipo']
    search_fields = ['nome_fantasia', 'sigla', 'email_comercial']
    ordering_fields = ['created_at', 'nome_fantasia']
    ordering = ['-created_at']

    # Ações customizadas

    @action(detail=True, methods=['post'])
    def bloquear(self, request, pk=None):
        empresa = self.get_object()
        empresa.ativo = False
        empresa.save(update_fields=['ativo'])
        
        # Criar notificação
        criar_notificacao_empresa_bloqueada(empresa, "Bloqueio manual pelo administrador")
        
        # Registra no histórico se houver assinatura ativa
        assinatura_ativa = empresa.assinatura_ativa
        if assinatura_ativa:
            registrar_historico_pagamento(
                assinatura=assinatura_ativa,
                tipo='BLOQUEIO',
                descricao=f'Empresa {empresa.nome_fantasia or empresa.razao_social} bloqueada',
                request=request,
                observacoes='Bloqueio manual realizado pelo administrador'
            )
        
        return Response({'status': 'Empresa bloqueada'})

    @action(detail=True, methods=['post'])
    def ativar(self, request, pk=None):
        """Ativa a empresa e (opcionalmente) atribui um novo plano."""
        empresa = self.get_object()

        plano_id = request.data.get('plano_id') or request.query_params.get('plano_id')

        # 1. Ativa empresa
        empresa_era_bloqueada = not empresa.ativo
        if empresa_era_bloqueada:
            empresa.ativo = True
            empresa.save(update_fields=['ativo'])

        # 2. Se não foi fornecido plano_id, somente ativa empresa
        if not plano_id:
            # Criar notificação se a empresa foi desbloqueada
            if empresa_era_bloqueada:
                criar_notificacao_empresa_ativada(empresa)
                
            # Registra no histórico se a empresa foi desbloqueada
            if empresa_era_bloqueada:
                assinatura_ativa = empresa.assinatura_ativa
                if assinatura_ativa:
                    registrar_historico_pagamento(
                        assinatura=assinatura_ativa,
                        tipo='DESBLOQUEIO',
                        descricao=f'Empresa {empresa.nome_fantasia or empresa.razao_social} desbloqueada',
                        request=request,
                        observacoes='Desbloqueio manual realizado pelo administrador'
                    )
            
            return Response({'status': 'Empresa ativada (sem alteração de plano)'})

        try:
            plano = Plano.objects.get(pk=plano_id)
        except Plano.DoesNotExist:
            return Response({'detail': 'Plano não encontrado'}, status=status.HTTP_400_BAD_REQUEST)

        # 3. Verifica se já existe uma assinatura ativa
        assinatura_existente = empresa.assinatura_ativa
        
        if assinatura_existente:
            # Se já tem uma assinatura ativa, apenas atualiza o plano se for diferente
            if assinatura_existente.plano.id != plano.id:
                # Salva dados anteriores para o histórico
                plano_anterior = assinatura_existente.plano
                data_fim_anterior = assinatura_existente.fim
                valor_anterior = assinatura_existente.plano.preco
                
                plano_anterior_nome = assinatura_existente.plano.nome
                assinatura_existente.plano = plano
                assinatura_existente.fim = assinatura_existente.inicio + relativedelta(days=plano.duracao_dias)
                assinatura_existente.ativa = True
                assinatura_existente.expirada = False
                assinatura_existente.save()
                
                # Registra no histórico
                registrar_historico_pagamento(
                    assinatura=assinatura_existente,
                    tipo='TROCA_PLANO',
                    descricao=f'Plano alterado de {plano_anterior_nome} para {plano.nome}',
                    request=request,
                    plano_anterior=plano_anterior,
                    plano_novo=plano,
                    data_fim_anterior=data_fim_anterior,
                    data_fim_nova=assinatura_existente.fim,
                    valor_anterior=valor_anterior,
                    valor_novo=plano.preco,
                    observacoes='Troca de plano durante ativação da empresa'
                )
                
                # Criar notificação
                criar_notificacao_plano_renovado(assinatura_existente, plano_anterior)
                
                return Response({
                    'status': f'Empresa ativada e plano atualizado de {plano_anterior_nome} para {plano.nome}'
                })
            else:
                # Se o plano é o mesmo, apenas reativa a assinatura
                assinatura_existente.ativa = True
                assinatura_existente.expirada = False
                assinatura_existente.save()
                
                # Registra no histórico
                registrar_historico_pagamento(
                    assinatura=assinatura_existente,
                    tipo='ATIVACAO',
                    descricao=f'Assinatura reativada para empresa {empresa.nome_fantasia or empresa.razao_social}',
                    request=request,
                    observacoes='Reativação de assinatura existente'
                )
                
                # Criar notificação
                criar_notificacao_empresa_ativada(empresa, plano.nome)
                
                return Response({
                    'status': f'Empresa ativada com plano {plano.nome} (já existente)'
                })
        else:
            # 4. Se não tem assinatura ativa, cria uma nova
            inicio = timezone.now()
            fim = inicio + relativedelta(days=plano.duracao_dias)
            nova_assinatura = Assinatura.objects.create(
                empresa=empresa,
                plano=plano,
                inicio=inicio,
                fim=fim,
                ativa=True,
                expirada=False,
            )
            
            # Registra no histórico
            registrar_historico_pagamento(
                assinatura=nova_assinatura,
                tipo='CRIACAO',
                descricao=f'Nova assinatura criada para empresa {empresa.nome_fantasia or empresa.razao_social}',
                request=request,
                plano_novo=plano,
                data_inicio_nova=inicio,
                data_fim_nova=fim,
                valor_novo=plano.preco,
                observacoes='Criação de nova assinatura durante ativação da empresa'
            )

            # Criar notificação
            criar_notificacao_assinatura_criada(nova_assinatura)
            criar_notificacao_empresa_ativada(empresa, plano.nome)

            return Response({'status': f'Empresa ativada com novo plano {plano.nome}'})

    @action(detail=True, methods=['post'])
    def expirar(self, request, pk=None):
        """Expira uma assinatura manualmente e bloqueia a empresa automaticamente."""
        try:
            assinatura = self.get_object()
            
            if assinatura.expirada:
                return Response(
                    {'error': 'Assinatura já está expirada'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Salva dados anteriores para o histórico
            data_fim_anterior = assinatura.fim
            
            assinatura.marcar_como_expirada()

            # Bloqueia a empresa automaticamente
            empresa = assinatura.empresa
            empresa_bloqueada = False
            if empresa.ativo:
                empresa.ativo = False
                empresa.save(update_fields=['ativo'])
                empresa_bloqueada = True
                
                # Criar notificação de empresa bloqueada
                criar_notificacao_empresa_bloqueada(empresa, "Bloqueio automático por expiração de plano")
            
            # Criar notificação de plano expirado
            criar_notificacao_plano_expirado(assinatura, "Expiração manual pelo administrador")
            
            # Registra no histórico
            registrar_historico_pagamento(
                assinatura=assinatura,
                tipo='EXPIRACAO',
                descricao=f'Plano {assinatura.plano.nome} expirado manualmente',
                request=request,
                data_fim_anterior=data_fim_anterior,
                observacoes='Expiração manual realizada pelo administrador'
            )
            
            return Response({
                'message': 'Assinatura expirada com sucesso',
                'assinatura_id': assinatura.id,
                'empresa': assinatura.empresa.nome_fantasia or assinatura.empresa.razao_social,
                'plano': assinatura.plano.nome,
                'empresa_bloqueada': empresa_bloqueada
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'error': 'Erro ao expirar assinatura', 'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'])
    def assinaturas(self, request, pk=None):
        """Retorna todas as assinaturas (pagamentos) da empresa, inclusive expiradas."""
        empresa = self.get_object()
        assinaturas = empresa.assinaturas.select_related('plano').all().order_by('-inicio')
        serializer = AssinaturaAdminSerializer(assinaturas, many=True)
        return Response(serializer.data)

    # Lista para react-admin: deve retornar {"data": [...]} e cabeçalho Content-Range
    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()
        serializer = self.get_serializer(qs, many=True)
        total = qs.count()
        if total:
            content_range = f'items 0-{total - 1}/{total}'
        else:
            content_range = 'items */0'
        headers = {
            'Content-Range': content_range
        }
        return Response(serializer.data, headers=headers)

    # O resto (retrieve, create, update) mantém o comportamento padrão do ModelViewSet,
    # retornando um objeto JSON único conforme esperado pelo simpleRestProvider.

    def update(self, request, *args, **kwargs):
        # Permitir atualizações parciais mesmo em requisições PUT/PATCH vindas do react-admin
        kwargs['partial'] = True
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """Exclui permanentemente a empresa e todos os dados vinculados (incluindo usuários exclusivos)."""
        empresa = self.get_object()
        
        User = get_user_model()
        
        # 1. Buscar usuários que possuem empresa_atual = empresa OU que estão em UserCompanyLink
        from usuariospainel.models import UserCompanyLink
        
        usuarios_emp_atual = set(User.objects.filter(empresa_atual=empresa))
        # Busca usuários vinculados via UserCompanyLink (related_name="company_links")
        usuarios_vinculos = set(User.objects.filter(company_links__empresa=empresa))
        usuarios_para_apagar = usuarios_emp_atual.union(usuarios_vinculos)
        
        # 2. Excluir vínculos UserCompanyLink
        UserCompanyLink.objects.filter(empresa=empresa).delete()
        
        # 3. Excluir Responsáveis vinculados
        empresa.responsaveis.all().delete()
        
        # 4. Excluir usuários que não têm mais vínculo com outras empresas
        deletados = 0
        for user in usuarios_para_apagar:
            # 4a. Sempre desvincula empresa_atual se for a que está sendo removida
            if user.empresa_atual == empresa:
                user.empresa_atual = None
                user.save(update_fields=['empresa_atual'])

            # 4b. Se for usuário PF, apenas mantemos a conta (não excluir)
            if user.user_type == 'PF':
                continue  # salta para o próximo usuário

            # 4c. Usuários PJ (proprietários da empresa)
            possui_outras_empresas = UserCompanyLink.objects.filter(user=user).exists()

            # Se não tem mais nenhum vínculo, podemos apagar completamente
            if not possui_outras_empresas:
                user.delete()
                deletados += 1
        
        # 5. Excluir a empresa (cascata remove endereços, assinaturas, etc.)
        # Usa razão social como nome preferencial; se não houver, usa nome fantasia, depois sigla ou ID
        empresa_nome = empresa.razao_social or empresa.nome_fantasia or empresa.sigla or str(empresa.id)
        empresa.delete()
        
        return Response(
            {
                'status': 'Empresa, usuários e vínculos excluídos permanentemente',
                'usuarios_excluidos': deletados,
                'message': f'Empresa "{empresa_nome}" e {deletados} usuário(s) foram removidos definitivamente.'
            },
            status=status.HTTP_200_OK
        )


# ---------------------- Novos Endpoints Analíticos ----------------------


class AdminAnalyticsAPIView(views.APIView):
    """Endpoint analítico com dados para gráficos do painel admin.

    Retorna:
    {
        "plans_distribution": {
            "TRIAL": 10,
            "BASIC": 15,
            "PRO": 5,
            "ENTERPRISE": 2
        },
        "revenue_by_month": [
            {"month": "2025-01", "total": 1234.56},
            ...
        ],
        "companies_created_by_month": [
            {"month": "2025-01", "total": 8},
            ...
        ]
    }
    """

    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        """Gera dados de distribuição de planos, receita mensal e novas empresas."""
        # 1. Distribuição de planos
        active_plans = Plano.objects.filter(ativo=True)
        plans_distribution = {}
        for plano in active_plans:
            count_empresas = Empresa.objects.filter(
                assinaturas__plano=plano,
                assinaturas__ativa=True,
                assinaturas__expirada=False
            ).distinct().count()
            plans_distribution[plano.codigo] = count_empresas

        # 2. Receita mensal total últimos 12 meses (com base em assinaturas criadas)
        hoje = timezone.now().date()
        inicio_periodo = hoje - relativedelta(months=12)

        from django.db.models.functions import TruncMonth
        from django.db.models import Sum, F

        receitas_queryset = (
            Assinatura.objects
            .filter(inicio__date__gte=inicio_periodo)
            .annotate(month=TruncMonth('inicio'))
            .values('month')
            .annotate(total=Sum(F('plano__preco')))
            .order_by('month')
        )

        # Normalizar para garantir 12 meses contíguos
        revenue_by_month = []
        for i in range(11, -1, -1):
            mes_referencia = hoje - relativedelta(months=i)
            mes_inicio = mes_referencia.replace(day=1)
            key = mes_inicio.replace(day=1)
            receita_obj = next((item for item in receitas_queryset if item['month'] == key), None)
            total = receita_obj['total'] if receita_obj else 0
            revenue_by_month.append({
                'month': key.strftime('%Y-%m'),
                'total': float(total) if total is not None else 0
            })

        # 3. Empresas criadas por mês (últimos 12 meses)
        empresas_queryset = (
            Empresa.objects
            .filter(created_at__date__gte=inicio_periodo)
            .annotate(month=TruncMonth('created_at'))
            .values('month')
            .annotate(total=models.Count('id'))
            .order_by('month')
        )

        companies_created_by_month = []
        for i in range(11, -1, -1):
            mes_referencia = hoje - relativedelta(months=i)
            mes_inicio = mes_referencia.replace(day=1)
            obj = next((item for item in empresas_queryset if item['month'] == mes_inicio.replace(day=1)), None)
            total = obj['total'] if obj else 0
            companies_created_by_month.append({
                'month': mes_inicio.strftime('%Y-%m'),
                'total': total
            })

        return Response({
            'plans_distribution': plans_distribution,
            'revenue_by_month': revenue_by_month,
            'companies_created_by_month': companies_created_by_month,
        })


# --------------------- Usuários PF ---------------------


class CustomPageNumberPagination(PageNumberPagination):
    page_size = 5
    page_size_query_param = 'page_size'
    max_page_size = 100


class PFUserAdminViewSet(viewsets.ModelViewSet):
    """CRUD completo de usuários PF para o painel admin."""

    permission_classes = [IsAuthenticated, IsAdminUser]
    pagination_class = None

    def get_queryset(self):
        User = get_user_model()
        qs = User.objects.filter(user_type='PF')

        admin_param = self.request.query_params.get('admin')  # ?admin=true para somente admins
        if admin_param in ('true', 'True', '1'):
            qs = qs.filter(models.Q(is_staff=True) | models.Q(is_superuser=True))
        elif admin_param in ('false', 'False', '0'):
            qs = qs.filter(is_staff=False, is_superuser=False)

        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(
                models.Q(email__icontains=search) |
                models.Q(username__icontains=search) |
                models.Q(person_profile__name__icontains=search)
            )
        return qs.order_by('-created_at')

    def get_serializer_class(self):
        if self.action in ('list', 'retrieve'):
            return PFUserAdminSerializer
        return PFUserAdminWriteSerializer

    # Content-Range header (compatível com react-admin)
    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()
        serializer = self.get_serializer(qs, many=True)
        total = qs.count()
        if total:
            content_range = f'items 0-{total - 1}/{total}'
        else:
            content_range = 'items */0'
        headers = {
            'Content-Range': content_range
        }
        return Response(serializer.data, headers=headers)

    # Permitir atualizações parciais (react-admin envia PUT completo, mas garantimos)
    def update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """Exclui permanentemente o usuário PF e todos os dados relacionados."""
        user = self.get_object()
        
        # Verifica se é um usuário PF
        if user.user_type != 'PF':
            return Response(
                {'error': 'Apenas usuários PF podem ser excluídos por este endpoint.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Coleta informações para o log
        user_info = {
            'id': user.id,
            'email': user.email,
            'username': user.username,
            'name': getattr(user.person_profile, 'name', None) if hasattr(user, 'person_profile') else None,
            'is_admin': user.is_staff or user.is_superuser
        }
        
        try:
            # 1. Remove vínculos com empresas (UserCompanyLink)
            from usuariospainel.models import UserCompanyLink
            vinculos_count = UserCompanyLink.objects.filter(user=user).count()
            UserCompanyLink.objects.filter(user=user).delete()
            
            # 2. Remove convites relacionados
            from convite_notificacao.models import ConviteUsuario
            convites_count = ConviteUsuario.objects.filter(email_convidado__iexact=user.email).count()
            ConviteUsuario.objects.filter(email_convidado__iexact=user.email).delete()
            
            # 3. Remove perfil de usuário (PersonProfile)
            if hasattr(user, 'person_profile'):
                user.person_profile.delete()
            
            # 4. Remove perfil geral (PerfilUsuario)
            from perfilusuario.models import PerfilUsuario
            try:
                perfil = PerfilUsuario.objects.get(usuario=user)
                perfil.delete()
            except PerfilUsuario.DoesNotExist:
                pass
            
            # 5. Remove o usuário principal (isso também remove o perfil PF por CASCADE)
            user.delete()
            
            return Response(
                {
                    'status': 'Usuário PF excluído permanentemente',
                    'user_info': user_info,
                    'dados_removidos': {
                        'vinculos_empresas': vinculos_count,
                        'convites': convites_count
                    },
                    'message': f'Usuário "{user_info["name"] or user_info["email"]}" foi excluído definitivamente do banco de dados.'
                },
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            return Response(
                {
                    'error': 'Erro ao excluir usuário',
                    'detail': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'])
    def empresas_vinculadas(self, request, pk=None):
        """Retorna todas as empresas vinculadas ao usuário PF."""
        try:
            user = self.get_object()
            
            # Verifica se é um usuário PF
            if user.user_type != 'PF':
                return Response(
                    {'error': 'Apenas usuários PF podem ter empresas vinculadas.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Busca vínculos com empresas
            from usuariospainel.models import UserCompanyLink
            vinculos = UserCompanyLink.objects.filter(user=user).select_related('empresa')
            
            empresas_data = []
            for vinculo in vinculos:
                empresa_data = {
                    'id': vinculo.empresa.id,
                    'nome_fantasia': vinculo.empresa.nome_fantasia,
                    'razao_social': vinculo.empresa.razao_social,
                    'sigla': vinculo.empresa.sigla,
                    'cargo': vinculo.position,
                    'status': vinculo.status,
                    'data_vinculo': vinculo.created_at.isoformat() if vinculo.created_at else None
                }
                empresas_data.append(empresa_data)
            
            return Response(empresas_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {
                    'error': 'Erro ao buscar empresas vinculadas',
                    'detail': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# --------------------- Pagamentos (Assinaturas) ---------------------


class AssinaturaAdminViewSet(viewsets.ModelViewSet):
    """CRUD completo de assinaturas para pagamentos."""

    serializer_class = AssinaturaAdminSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    pagination_class = None

    def get_queryset(self):
        # Parâmetros de filtro
        status_param = self.request.query_params.get('status')
        plano_param = self.request.query_params.get('plano')
        search = self.request.query_params.get('search')

        # Lógica: para cada empresa, retorna apenas a assinatura/plano atual (ativa, bloqueada ou última expirada)
        from django.db.models import OuterRef, Subquery
        empresas = Empresa.objects.all()
        assinatura_ativas = Assinatura.objects.filter(
            empresa=OuterRef('pk'), ativa=True, expirada=False
        ).order_by('-inicio')
        assinatura_ultimas = Assinatura.objects.filter(
            empresa=OuterRef('pk')
        ).order_by('-inicio')

        empresas = empresas.annotate(
            assinatura_id=Subquery(assinatura_ativas.values('id')[:1])
        )
        empresas = empresas.annotate(
            assinatura_id_final=Subquery(
                Assinatura.objects.filter(
                    empresa=OuterRef('pk'),
                    id=models.Case(
                        models.When(id=Subquery(assinatura_ativas.values('id')[:1]), then=Subquery(assinatura_ativas.values('id')[:1])),
                        default=Subquery(assinatura_ultimas.values('id')[:1]),
                        output_field=models.IntegerField()
                    )
                ).values('id')[:1]
            )
        )
        assinatura_ids = []
        for empresa in empresas:
            assinatura_id = empresa.assinatura_id
            if not assinatura_id:
                ultima_assinatura = Assinatura.objects.filter(empresa=empresa).order_by('-inicio').first()
                if ultima_assinatura:
                    assinatura_id = ultima_assinatura.id
            if assinatura_id:
                assinatura_ids.append(assinatura_id)
        qs = Assinatura.objects.filter(id__in=assinatura_ids).select_related('empresa', 'plano').order_by('-inicio')

        # Agora aplica os filtros sobre a assinatura/plano atual de cada empresa
        if status_param:
            if status_param == 'ativa':
                qs = qs.filter(ativa=True, expirada=False, empresa__ativo=True)
            elif status_param == 'expirado':
                qs = qs.filter(expirada=True, empresa__ativo=True)
            elif status_param == 'reembolsado':
                qs = qs.filter(expirada=True, empresa__ativo=True)
            elif status_param == 'bloqueado':
                qs = qs.filter(empresa__ativo=False)
        if plano_param:
            qs = qs.filter(plano__id=plano_param)
        if search:
            qs = qs.filter(
                models.Q(empresa__nome_fantasia__icontains=search) |
                models.Q(empresa__razao_social__icontains=search) |
                models.Q(empresa__sigla__icontains=search) |
                models.Q(plano__nome__icontains=search)
            )
        return qs.order_by('-inicio')

    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()
        serializer = self.get_serializer(qs, many=True)
        total = qs.count()
        content_range = f'items 0-{total - 1}/{total}' if total else 'items */0'
        headers = {'Content-Range': content_range}
        return Response(serializer.data, headers=headers)

    def retrieve(self, request, *args, **kwargs):
        """Retorna uma assinatura específica com dados completos."""
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        """Cria uma nova assinatura."""
        try:
            empresa_id = request.data.get('empresa')
            plano_id = request.data.get('plano')
            inicio = request.data.get('inicio')
            observacoes = request.data.get('observacoes', '')
            
            if not empresa_id:
                return Response(
                    {'error': 'ID da empresa é obrigatório'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if not plano_id:
                return Response(
                    {'error': 'ID do plano é obrigatório'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            try:
                empresa = Empresa.objects.get(id=empresa_id)
            except Empresa.DoesNotExist:
                return Response(
                    {'error': 'Empresa não encontrada'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            try:
                plano = Plano.objects.get(id=plano_id)
            except Plano.DoesNotExist:
                return Response(
                    {'error': 'Plano não encontrado'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Desativar assinaturas ativas da empresa
            Assinatura.objects.filter(
                empresa=empresa,
                ativa=True,
                expirada=False
            ).update(ativa=False)
            
            # Calcular data de início
            if inicio:
                data_inicio = timezone.datetime.strptime(inicio, '%Y-%m-%d').replace(tzinfo=timezone.utc)
            else:
                data_inicio = timezone.now()
            
            # Calcular data de fim
            data_fim = data_inicio + relativedelta(days=plano.duracao_dias)
            
            # Criar nova assinatura
            nova_assinatura = Assinatura.objects.create(
                empresa=empresa,
                plano=plano,
                inicio=data_inicio,
                fim=data_fim,
                ativa=True,
                expirada=False,
                observacoes=observacoes
            )
            
            # Criar notificações
            criar_notificacao_empresa_ativada(empresa, plano.nome)
            criar_notificacao_assinatura_criada(nova_assinatura)
            criar_notificacao_pagamento_recebido(nova_assinatura, plano.preco, "Novo pagamento")
            
            serializer = self.get_serializer(nova_assinatura)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response(
                {'error': 'Erro ao criar assinatura', 'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def update(self, request, *args, **kwargs):
        """Atualiza uma assinatura existente."""
        try:
            instance = self.get_object()
            
            # Atualizar campos permitidos
            if 'empresa' in request.data:
                try:
                    empresa = Empresa.objects.get(id=request.data['empresa'])
                    instance.empresa = empresa
                except Empresa.DoesNotExist:
                    return Response(
                        {'error': 'Empresa não encontrada'},
                        status=status.HTTP_404_NOT_FOUND
                    )
            
            if 'plano' in request.data:
                try:
                    plano = Plano.objects.get(id=request.data['plano'])
                    instance.plano = plano
                except Plano.DoesNotExist:
                    return Response(
                        {'error': 'Plano não encontrado'},
                        status=status.HTTP_404_NOT_FOUND
                    )
            
            if 'inicio' in request.data:
                instance.inicio = timezone.datetime.strptime(request.data['inicio'], '%Y-%m-%d').replace(tzinfo=timezone.utc)
            
            if 'fim' in request.data:
                instance.fim = timezone.datetime.strptime(request.data['fim'], '%Y-%m-%d').replace(tzinfo=timezone.utc)
            
            if 'ativa' in request.data:
                instance.ativa = request.data['ativa']
            
            if 'expirada' in request.data:
                instance.expirada = request.data['expirada']
            
            if 'observacoes' in request.data:
                instance.observacoes = request.data['observacoes']
            
            instance.save()
            serializer = self.get_serializer(instance)
            return Response(serializer.data)
            
        except Exception as e:
            return Response(
                {'error': 'Erro ao atualizar assinatura', 'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def destroy(self, request, *args, **kwargs):
        """Exclui uma assinatura."""
        try:
            instance = self.get_object()
            instance.delete()
            return Response(
                {'message': 'Assinatura excluída com sucesso'},
                status=status.HTTP_204_NO_CONTENT
            )
        except Exception as e:
            return Response(
                {'error': 'Erro ao excluir assinatura', 'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def atualizar_plano(self, request, pk=None):
        """Atualiza o plano de uma assinatura."""
        try:
            assinatura = self.get_object()
            plano_id = request.data.get('plano_id')
            
            if not plano_id:
                return Response(
                    {'error': 'ID do plano é obrigatório'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            try:
                novo_plano = Plano.objects.get(id=plano_id)
            except Plano.DoesNotExist:
                return Response(
                    {'error': 'Plano não encontrado'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Se o plano for o mesmo, não faz nada
            if assinatura.plano.id == novo_plano.id:
                return Response({
                    'message': 'A assinatura já possui este plano',
                    'assinatura_id': assinatura.id,
                    'plano': assinatura.plano.nome
                }, status=status.HTTP_200_OK)
            
            # Salva dados anteriores para o histórico
            plano_anterior = assinatura.plano
            data_inicio_anterior = assinatura.inicio
            data_fim_anterior = assinatura.fim
            valor_anterior = assinatura.plano.preco
            
            # Atualiza o plano da assinatura existente
            assinatura.plano = novo_plano
            
            # Recalcula a data de fim baseada na duração do novo plano
            # Mantém a data de início original, mas ajusta o fim
            assinatura.fim = assinatura.inicio + relativedelta(days=novo_plano.duracao_dias)
            
            # Se a nova data de fim já passou, marca como expirada
            if assinatura.fim <= timezone.now():
                assinatura.marcar_como_expirada()
            else:
                # Garante que a assinatura esteja ativa
                assinatura.ativa = True
                assinatura.expirada = False
            
            assinatura.save()
            
            # Registra no histórico
            registrar_historico_pagamento(
                assinatura=assinatura,
                tipo='TROCA_PLANO',
                descricao=f'Plano alterado de {plano_anterior.nome} para {novo_plano.nome}',
                request=request,
                plano_anterior=plano_anterior,
                plano_novo=novo_plano,
                data_inicio_anterior=data_inicio_anterior,
                data_fim_anterior=data_fim_anterior,
                data_inicio_nova=assinatura.inicio,
                data_fim_nova=assinatura.fim,
                valor_anterior=valor_anterior,
                valor_novo=novo_plano.preco,
                observacoes='Troca de plano realizada pelo administrador'
            )
            
            # Criar notificações
            criar_notificacao_plano_renovado(assinatura, plano_anterior)
            
            return Response({
                'message': 'Plano atualizado com sucesso',
                'assinatura_id': assinatura.id,
                'empresa': assinatura.empresa.nome_fantasia or assinatura.empresa.razao_social,
                'plano_anterior': plano_anterior.nome,
                'plano_novo': novo_plano.nome,
                'data_fim_nova': assinatura.fim.isoformat(),
                'expirada': assinatura.expirada
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'error': 'Erro ao atualizar plano', 'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def expirar(self, request, pk=None):
        """Expira uma assinatura manualmente e bloqueia a empresa automaticamente."""
        try:
            assinatura = self.get_object()
            
            if assinatura.expirada:
                return Response(
                    {'error': 'Assinatura já está expirada'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Salva dados anteriores para o histórico
            data_fim_anterior = assinatura.fim
            
            assinatura.marcar_como_expirada()

            # Bloqueia a empresa automaticamente
            empresa = assinatura.empresa
            empresa_bloqueada = False
            if empresa.ativo:
                empresa.ativo = False
                empresa.save(update_fields=['ativo'])
                empresa_bloqueada = True
                
                # Criar notificações
                criar_notificacao_empresa_ativada(empresa, assinatura.plano.nome)
                criar_notificacao_plano_expirado(assinatura, "Expiração manual pelo administrador")
                
                # Registra no histórico
                registrar_historico_pagamento(
                    assinatura=assinatura,
                    tipo='EXPIRACAO',
                    descricao=f'Plano {assinatura.plano.nome} expirado manualmente',
                    request=request,
                    data_fim_anterior=data_fim_anterior,
                    observacoes='Expiração manual realizada pelo administrador'
                )
            
            return Response({
                'message': 'Assinatura expirada com sucesso',
                'assinatura_id': assinatura.id,
                'empresa': assinatura.empresa.nome_fantasia or assinatura.empresa.razao_social,
                'plano': assinatura.plano.nome,
                'empresa_bloqueada': empresa_bloqueada
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'error': 'Erro ao expirar assinatura', 'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def reativar(self, request, pk=None):
        """Reativa uma assinatura expirada criando uma nova assinatura/ciclo."""
        try:
            assinatura_antiga = self.get_object()

            if not assinatura_antiga.expirada:
                return Response(
                    {'error': 'Assinatura não está expirada'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            empresa = assinatura_antiga.empresa
            plano = assinatura_antiga.plano
            dias_adicional = request.data.get('dias_adicional', plano.duracao_dias)
            agora = timezone.now()
            inicio_novo = agora
            fim_novo = agora + timezone.timedelta(days=dias_adicional)

            # Cria nova assinatura
            nova_assinatura = Assinatura.objects.create(
                empresa=empresa,
                plano=plano,
                inicio=inicio_novo,
                fim=fim_novo,
                ativa=True,
                expirada=False,
                observacoes=f'Reativação de ciclo a partir da assinatura expirada {assinatura_antiga.id}'
            )

            # Registra histórico na assinatura antiga
            registrar_historico_pagamento(
                assinatura=assinatura_antiga,
                tipo='EXPIRACAO',
                descricao=f'Assinatura expirada e novo ciclo criado (ID nova: {nova_assinatura.id})',
                request=request,
                data_fim_anterior=assinatura_antiga.fim,
                observacoes='Expiração e criação de novo ciclo por reativação'
            )

            # Registra histórico na nova assinatura
            registrar_historico_pagamento(
                assinatura=nova_assinatura,
                tipo='CRIACAO',
                descricao=f'Nova assinatura criada por reativação do ciclo anterior (ID antigo: {assinatura_antiga.id})',
                request=request,
                data_inicio_nova=nova_assinatura.inicio,
                data_fim_nova=nova_assinatura.fim,
                observacoes='Ciclo criado por reativação/renovação'
            )

            # Ativa a empresa se estiver bloqueada
            empresa_ativada = False
            if not empresa.ativo:
                empresa.ativo = True
                empresa.save(update_fields=['ativo'])
                empresa_ativada = True
                
                # Criar notificações
                criar_notificacao_empresa_ativada(empresa, plano.nome)
                criar_notificacao_assinatura_criada(nova_assinatura)
                criar_notificacao_pagamento_recebido(nova_assinatura, plano.preco, "Novo pagamento")

            # Criar notificação de assinatura criada
            criar_notificacao_assinatura_criada(nova_assinatura)

            return Response({
                'message': 'Nova assinatura criada com sucesso',
                'assinatura_id': nova_assinatura.id,
                'empresa': empresa.nome_fantasia or empresa.razao_social,
                'plano': plano.nome,
                'nova_data_inicio': nova_assinatura.inicio.isoformat(),
                'nova_data_fim': nova_assinatura.fim.isoformat(),
                'empresa_ativada': empresa_ativada
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response(
                {'error': 'Erro ao reativar assinatura', 'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'])
    def historico(self, request, pk=None):
        """Retorna o histórico de mudanças da assinatura."""
        try:
            assinatura = self.get_object()
            historico = assinatura.historico.all()
            serializer = HistoricoPagamentoSerializer(historico, many=True)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {'error': 'Erro ao buscar histórico', 'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def criar_novo_pagamento(self, request, pk=None):
        """Cria um novo pagamento quando o plano está expirado e a empresa bloqueada."""
        try:
            assinatura_antiga = self.get_object()
            plano_id = request.data.get('plano_id')
            
            if not plano_id:
                return Response(
                    {'error': 'ID do plano é obrigatório'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            try:
                novo_plano = Plano.objects.get(id=plano_id)
            except Plano.DoesNotExist:
                return Response(
                    {'error': 'Plano não encontrado'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Verifica se o plano está expirado e a empresa bloqueada
            if not assinatura_antiga.expirada:
                return Response(
                    {'error': 'Apenas planos expirados podem gerar novos pagamentos'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            empresa = assinatura_antiga.empresa
            if empresa.ativo:
                return Response(
                    {'error': 'Apenas empresas bloqueadas podem gerar novos pagamentos'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Cria nova assinatura com data atual
            agora = timezone.now()
            inicio_novo = agora
            fim_novo = agora + relativedelta(days=novo_plano.duracao_dias)
            
            nova_assinatura = Assinatura.objects.create(
                empresa=empresa,
                plano=novo_plano,
                inicio=inicio_novo,
                fim=fim_novo,
                ativa=True,
                expirada=False,
                observacoes=f'Novo pagamento criado após expiração do plano anterior (ID: {assinatura_antiga.id})'
            )
            
            # Desbloqueia a empresa automaticamente
            empresa.ativo = True
            empresa.save(update_fields=['ativo'])
            
            # Criar notificações
            criar_notificacao_empresa_ativada(empresa, novo_plano.nome)
            criar_notificacao_assinatura_criada(nova_assinatura)
            criar_notificacao_pagamento_recebido(nova_assinatura, novo_plano.preco, "Novo pagamento")
            
            # Registra histórico na assinatura antiga
            registrar_historico_pagamento(
                assinatura=assinatura_antiga,
                tipo='EXPIRACAO',
                descricao=f'Plano expirado e novo pagamento criado (ID novo: {nova_assinatura.id})',
                request=request,
                data_fim_anterior=assinatura_antiga.fim,
                observacoes='Expiração e criação de novo pagamento separado'
            )
            
            return Response({
                'message': f'Novo pagamento criado com sucesso para {novo_plano.nome}',
                'novo_pagamento_id': nova_assinatura.id,
                'assinatura_anterior_id': assinatura_antiga.id,
                'plano_anterior': assinatura_antiga.plano.nome,
                'plano_novo': novo_plano.nome,
                'valor_anterior': float(assinatura_antiga.plano.preco),
                'valor_novo': float(novo_plano.preco),
                'nova_data_inicio': nova_assinatura.inicio.isoformat(),
                'nova_data_fim': nova_assinatura.fim.isoformat(),
                'empresa_desbloqueada': True
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response(
                {'error': 'Erro ao criar novo pagamento', 'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def planos_disponiveis(self, request):
        """Retorna lista de planos disponíveis para filtro."""
        try:
            planos = Plano.objects.filter(ativo=True).order_by('nome')
            return Response([{
                'id': plano.id,
                'nome': plano.nome,
                'codigo': plano.codigo,
                'preco': float(plano.preco)
            } for plano in planos])
        except Exception as e:
            return Response(
                {'error': 'Erro ao buscar planos', 'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# --------------------- Planos CRUD ---------------------


class PlanoAdminViewSet(viewsets.ModelViewSet):
    """CRUD completo de planos"""

    queryset = Plano.objects.all()
    serializer_class = PlanoAdminSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    pagination_class = None

    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['nome', 'codigo']
    ordering_fields = ['preco', 'duracao_dias', 'nome']
    ordering = ['nome']

    def get_queryset(self):
        qs = Plano.objects.all()
        ativo_param = self.request.query_params.get('ativo')
        if ativo_param is not None and ativo_param != '':
            if ativo_param.lower() == 'true':
                qs = qs.filter(ativo=True)
            elif ativo_param.lower() == 'false':
                qs = qs.filter(ativo=False)
        return qs

    # Aceitar PUT parcial (simpleRestProvider envia todos campos, mas se faltar algo, continua)
    def update(self, request, *args, **kwargs):
        # Permitir atualizações parciais mesmo em requisições PUT/PATCH vindas do react-admin
        kwargs['partial'] = True
        return super().update(request, *args, **kwargs)

    # Após salvar o plano, atualiza a data de fim de assinaturas ativas desse plano
    def perform_update(self, serializer):
        instance = serializer.save()

        from assinaturas.models import Assinatura  # import interno para evitar ciclos
        assinaturas_ativas = Assinatura.objects.filter(plano=instance, ativa=True, expirada=False)

        if assinaturas_ativas.exists():
            for assinatura in assinaturas_ativas:
                assinatura.fim = assinatura.inicio + relativedelta(days=instance.duracao_dias)
                # Se a nova data de fim já passou, marca como expirada
                if assinatura.fim <= timezone.now():
                    assinatura.marcar_como_expirada()
                else:
                    assinatura.save(update_fields=['fim'])
        return instance

    # React-admin expects Content-Range header
    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(qs, many=True)
        total = qs.count()
        content_range = f'items 0-{total - 1}/{total}' if total else 'items */0'
        headers = {'Content-Range': content_range}
        return Response(serializer.data, headers=headers)


# --------------------- Notificações ---------------------


class NotificacaoAdminViewSet(viewsets.ModelViewSet):
    """ViewSet para gerenciar notificações do admin"""
    
    serializer_class = NotificacaoAdminSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    pagination_class = None
    
    def get_queryset(self):
        """Filtra notificações baseado nos parâmetros"""
        queryset = NotificacaoAdmin.objects.all()
        
        # Filtro por status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filtro por tipo
        tipo_filter = self.request.query_params.get('tipo')
        if tipo_filter:
            queryset = queryset.filter(tipo=tipo_filter)
        
        # Filtro por prioridade
        prioridade_filter = self.request.query_params.get('prioridade')
        if prioridade_filter:
            queryset = queryset.filter(prioridade=prioridade_filter)
        
        # Filtro por empresa
        empresa_filter = self.request.query_params.get('empresa')
        if empresa_filter:
            queryset = queryset.filter(empresa_id=empresa_filter)
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def marcar_como_lida(self, request, pk=None):
        """Marca uma notificação como lida"""
        notificacao = self.get_object()
        notificacao.marcar_como_lida()
        return Response({'status': 'marcada como lida'})
    
    @action(detail=True, methods=['post'])
    def arquivar(self, request, pk=None):
        """Arquiva uma notificação"""
        notificacao = self.get_object()
        notificacao.arquivar()
        return Response({'status': 'arquivada'})
    
    @action(detail=False, methods=['post'])
    def marcar_todas_como_lidas(self, request):
        """Marca todas as notificações não lidas como lidas"""
        NotificacaoAdmin.objects.filter(status='nao_lida').update(
            status='lida',
            lida_em=timezone.now()
        )
        return Response({'status': 'todas marcadas como lidas'})
    
    @action(detail=False, methods=['get'])
    def contador(self, request):
        """Retorna contadores de notificações"""
        total = NotificacaoAdmin.objects.count()
        nao_lidas = NotificacaoAdmin.objects.filter(status='nao_lida').count()
        criticas = NotificacaoAdmin.objects.filter(
            status='nao_lida',
            prioridade='critica'
        ).count()
        
        return Response({
            'total': total,
            'nao_lidas': nao_lidas,
            'criticas': criticas
        })
    
    @action(detail=False, methods=['get'])
    def recentes(self, request):
        """Retorna notificações recentes (últimas 10)"""
        notificacoes = self.get_queryset()[:10]
        serializer = self.get_serializer(notificacoes, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['delete'])
    def excluir(self, request, pk=None):
        """Exclui uma notificação específica"""
        notificacao = self.get_object()
        notificacao.delete()
        return Response({'status': 'excluida'})

    @action(detail=False, methods=['delete'])
    def excluir_todas(self, request):
        """Exclui todas as notificações do sistema"""
        NotificacaoAdmin.objects.all().delete()
        return Response({'status': 'todas excluidas'})
