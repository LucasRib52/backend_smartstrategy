from django.shortcuts import render
from rest_framework import viewsets, permissions
from .models import Plano
from .serializers import PlanoSerializer
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status as http_status
from rest_framework import permissions
from asaas.services import AsaasService
from .models import Assinatura

# Create your views here.

class PlanoViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Plano.objects.all()
    serializer_class = PlanoSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = None

    def get_queryset(self):
        return Plano.objects.filter(ativo=True).order_by('nome')


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def subscription_status(request):
    subscription_id = request.query_params.get('subscription_id')
    if not subscription_id:
        return Response({'error': 'subscription_id é obrigatório'}, status=http_status.HTTP_400_BAD_REQUEST)
    service = AsaasService()
    try:
        data = service.get_subscription_status(subscription_id)
    except Exception as e:
        return Response({'error': str(e)}, status=http_status.HTTP_500_INTERNAL_SERVER_ERROR)
    status_value = data.get('status')
    paid = status_value == 'ACTIVE'
    return Response({'subscription_status': status_value, 'paid': paid, 'data': data}, status=http_status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def simulate_payment_webhook(request):
    """Simula webhook de pagamento recebido para testes"""
    subscription_id = request.data.get('subscription_id')
    if not subscription_id:
        return Response({'error': 'subscription_id é obrigatório'}, status=http_status.HTTP_400_BAD_REQUEST)
    
    # Simula payload do webhook PAYMENT_RECEIVED
    webhook_payload = {
        'event': 'PAYMENT_RECEIVED',
        'payment': {
            'id': 'test_payment_id',
            'subscription': subscription_id,
            'status': 'CONFIRMED',
            'value': 100.00,
            'dueDate': '2025-09-13'
        }
    }
    
    from asaas.services import AsaasService
    service = AsaasService()
    try:
        success = service.process_webhook(webhook_payload)
        if success:
            return Response({'message': 'Webhook processado com sucesso'}, status=http_status.HTTP_200_OK)
        else:
            return Response({'error': 'Erro ao processar webhook'}, status=http_status.HTTP_500_INTERNAL_SERVER_ERROR)
    except Exception as e:
        return Response({'error': str(e)}, status=http_status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def upgrade_subscription(request):
    """Realiza ou simula upgrade/downgrade de plano com cálculo de pró-rata."""
    empresa_id = request.data.get('empresa_id')
    novo_plano_id = request.data.get('novo_plano_id')
    confirmar = bool(request.data.get('confirmar', False))

    if not empresa_id or not novo_plano_id:
        return Response({'error': 'empresa_id e novo_plano_id são obrigatórios'}, status=http_status.HTTP_400_BAD_REQUEST)

    from empresas.models import Empresa
    from assinaturas.models import Assinatura, Plano
    from assinaturas.utils import calcular_prorata
    from django.utils import timezone

    try:
        empresa = Empresa.objects.get(id=empresa_id)
    except Empresa.DoesNotExist:
        return Response({'error': 'Empresa não encontrada'}, status=http_status.HTTP_404_NOT_FOUND)

    assinatura = Assinatura.objects.filter(empresa=empresa, ativa=True).first()
    if not assinatura:
        return Response({'error': 'Empresa não possui assinatura ativa'}, status=http_status.HTTP_400_BAD_REQUEST)

    try:
        novo_plano = Plano.objects.get(id=novo_plano_id, ativo=True)
    except Plano.DoesNotExist:
        return Response({'error': 'Novo plano não encontrado'}, status=http_status.HTTP_404_NOT_FOUND)

    hoje = timezone.now().date()
    dias_restantes = max((assinatura.fim.date() - hoje).days, 0)
    duracao_ciclo = max((assinatura.fim.date() - assinatura.inicio.date()).days, 1)

    valor_prorata = calcular_prorata(assinatura.plano.preco, novo_plano.preco, dias_restantes, duracao_ciclo)

    response_data = {
        'empresa': empresa.nome_fantasia or empresa.razao_social,
        'plano_atual': {
            'id': assinatura.plano.id,
            'nome': assinatura.plano.nome,
            'preco': str(assinatura.plano.preco),
        },
        'novo_plano': {
            'id': novo_plano.id,
            'nome': novo_plano.nome,
            'preco': str(novo_plano.preco),
            'duracao_dias': novo_plano.duracao_dias,
        },
        'dias_restantes': dias_restantes,
        'duracao_ciclo': duracao_ciclo,
        'valor_prorata': str(valor_prorata),
        'cobranca_necessaria': valor_prorata > 0,
    }

    if not confirmar:
        return Response({'success': True, 'simulated': True, **response_data}, status=http_status.HTTP_200_OK)

    # Confirmado – executa a troca
    try:
        from asaas.services import AsaasService
        service = AsaasService()

        # Cria pagamento da diferença se houver troca para plano mais caro
        payment_link = None
        if valor_prorata > 0:
            # Usa a data de vencimento da assinatura atual
            # Define vencimento da cobrança para coincidir com o novo ciclo completo
            from datetime import timedelta
            due_date = (timezone.now().date() + timedelta(days=novo_plano.duracao_dias)).strftime('%Y-%m-%d')
            
            # Cria uma cobrança simples para a diferença
            payment_resp = service.create_simple_payment(
                customer_id=empresa.asaas_customer_id or assinatura.asaas_customer_id,
                value=float(valor_prorata),
                description=f'Diferença de upgrade para plano {novo_plano.nome}',
                due_date=due_date,
                external_reference=f'UPGRADE_{assinatura.id}'
            )
            payment_link = payment_resp.get('invoiceUrl') or payment_resp.get('bankSlipUrl')
            
            # Cria a nova assinatura no nosso sistema (sem asaas_subscription_id ainda)
            from assinaturas.models import Assinatura
            nova_assinatura = Assinatura.objects.create(
                empresa=empresa,
                plano=novo_plano,
                asaas_subscription_id=None,  # Será preenchido quando pagamento for confirmado
                asaas_customer_id=empresa.asaas_customer_id,
                payment_status='PENDING',
                trial_end_date=None,
                fim=assinatura.fim,  # Mantém a data de fim da assinatura atual
                next_payment_date=assinatura.next_payment_date,
                ativa=False,
                expirada=False
            )
            
            # Salva o ID do pagamento na nova assinatura para referência
            nova_assinatura.observacoes = f"Upgrade Payment ID: {payment_resp.get('id')}"
            nova_assinatura.save(update_fields=['observacoes'])
        else:
            # Upgrade gratuito - cria a nova assinatura imediatamente
            subscription_resp = service.create_subscription(empresa, novo_plano, extra_days=0)
            
            # Não cancela a antiga no Asaas aqui. Cancela apenas após ativação da nova (webhook SUBSCRIPTION_ACTIVATED)
            assinatura.ativa = False
            assinatura.payment_status = 'CANCELLED'
            assinatura.expirada = True
            assinatura.save(update_fields=['ativa','payment_status','expirada'])

        response_data.update({
            'success': True,
            'simulated': False,
            'payment_link': payment_link,
            'nova_subscription_id': subscription_resp.get('id') if valor_prorata <= 0 else None,
        })
        return Response(response_data, status=http_status.HTTP_201_CREATED)

    except Exception as e:
        return Response({'error': str(e)}, status=http_status.HTTP_500_INTERNAL_SERVER_ERROR)
