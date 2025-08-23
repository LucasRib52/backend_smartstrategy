import json
import hmac
import hashlib
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .services import AsaasService
from .models import AsaasWebhook

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class AsaasWebhookTestView(APIView):
    """
    View para testar webhook do Asaas
    """
    permission_classes = []  # Não exige autenticação
    
    def get(self, request):
        """
        Testa se o endpoint está funcionando
        """
        return Response({
            'status': 'ok',
            'message': 'Webhook endpoint funcionando'
        }, status=status.HTTP_200_OK)
    
    def post(self, request):
        """
        Testa webhook com payload simulado
        """
        try:
            payload = request.data
            logger.info(f"Teste de webhook recebido: {payload}")
            
            # Processa o webhook
            asaas_service = AsaasService()
            success = asaas_service.process_webhook(payload)
            
            if success:
                return Response({
                    'status': 'success',
                    'message': 'Webhook processado com sucesso'
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'status': 'error',
                    'message': 'Erro ao processar webhook'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
        except Exception as e:
            logger.error(f"Erro no teste de webhook: {str(e)}")
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@method_decorator(csrf_exempt, name='dispatch')
class AsaasWebhookView(APIView):
    """
    View para receber webhooks do Asaas
    """
    permission_classes = []  # Não exige autenticação
    
    def post(self, request):
        """
        Processa webhook recebido do Asaas
        """
        try:
            # Log dos headers
            logger.info(f"Headers recebidos: {dict(request.headers)}")
            
            # Obtém o payload
            payload = json.loads(request.body)
            logger.info(f"Payload recebido: {payload}")
            
            # Valida a assinatura do webhook (opcional, mas recomendado)
            # Temporariamente desabilitado para testes
            # if not self._validate_webhook_signature(request):
            #     logger.warning("Assinatura do webhook inválida")
            #     return Response(
            #         {'error': 'Assinatura inválida'}, 
            #         status=status.HTTP_400_BAD_REQUEST
            #     )
            
            # Processa o webhook
            asaas_service = AsaasService()
            success = asaas_service.process_webhook(payload)
            
            if success:
                logger.info(f"Webhook processado com sucesso: {payload.get('event')}")
                return Response({'status': 'success'}, status=status.HTTP_200_OK)
            else:
                logger.error(f"Erro ao processar webhook: {payload}")
                return Response(
                    {'error': 'Erro ao processar webhook'}, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
                
        except json.JSONDecodeError as e:
            logger.error(f"Erro ao decodificar JSON do webhook: {str(e)}")
            return Response(
                {'error': 'JSON inválido'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Erro inesperado ao processar webhook: {str(e)}")
            return Response(
                {'error': 'Erro interno'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _validate_webhook_signature(self, request):
        """
        Valida a assinatura do webhook do Asaas
        """
        try:
            # Obtém a assinatura do header
            signature = request.headers.get('Asaas-Access-Token')
            
            if not signature:
                logger.warning("Header de assinatura não encontrado")
                return False
            
            # Compara com o secret configurado
            expected_signature = settings.ASAAS_WEBHOOK_SECRET
            
            # Para simplificar, vamos apenas verificar se o token está presente
            # Em produção, você deve implementar a validação HMAC completa
            return signature == expected_signature
            
        except Exception as e:
            logger.error(f"Erro ao validar assinatura: {str(e)}")
            return False


class AsaasCustomerView(APIView):
    """
    View para gerenciar clientes no Asaas
    """
    
    def post(self, request):
        """
        Cria um cliente no Asaas
        """
        try:
            empresa_id = request.data.get('empresa_id')
            
            if not empresa_id:
                return Response(
                    {'error': 'empresa_id é obrigatório'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            from empresas.models import Empresa
            
            empresa = Empresa.objects.get(id=empresa_id)
            
            asaas_service = AsaasService()
            customer_data = asaas_service.create_customer(empresa)
            
            return Response({
                'success': True,
                'customer_id': customer_data.get('id'),
                'message': 'Cliente criado com sucesso no Asaas'
            }, status=status.HTTP_201_CREATED)
            
        except Empresa.DoesNotExist:
            return Response(
                {'error': 'Empresa não encontrada'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Erro ao criar cliente no Asaas: {str(e)}")
            return Response(
                {'error': 'Erro ao criar cliente'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AsaasSubscriptionView(APIView):
    """
    View para gerenciar assinaturas no Asaas
    """
    
    def post(self, request):
        """
        Cria uma assinatura no Asaas
        """
        try:
            empresa_id = request.data.get('empresa_id')
            plano_id = request.data.get('plano_id')
            
            if not empresa_id or not plano_id:
                return Response(
                    {'error': 'empresa_id e plano_id são obrigatórios'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            from empresas.models import Empresa
            from assinaturas.models import Plano
            
            empresa = Empresa.objects.get(id=empresa_id)
            plano = Plano.objects.get(id=plano_id)
            
            asaas_service = AsaasService()
            subscription_data = asaas_service.create_subscription(empresa, plano)
            
            return Response({
                'success': True,
                'subscription_id': subscription_data.get('id'),
                'message': 'Assinatura criada com sucesso no Asaas'
            }, status=status.HTTP_201_CREATED)
            
        except (Empresa.DoesNotExist, Plano.DoesNotExist):
            return Response(
                {'error': 'Empresa ou plano não encontrado'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Erro ao criar assinatura no Asaas: {str(e)}")
            return Response(
                {'error': 'Erro ao criar assinatura'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def delete(self, request, subscription_id):
        """
        Cancela uma assinatura no Asaas
        """
        try:
            from assinaturas.models import Assinatura
            
            assinatura = Assinatura.objects.get(asaas_subscription_id=subscription_id)
            
            asaas_service = AsaasService()
            asaas_service.cancel_subscription(assinatura)
            
            return Response({
                'success': True,
                'message': 'Assinatura cancelada com sucesso'
            }, status=status.HTTP_200_OK)
            
        except Assinatura.DoesNotExist:
            return Response(
                {'error': 'Assinatura não encontrada'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Erro ao cancelar assinatura: {str(e)}")
            return Response(
                {'error': 'Erro ao cancelar assinatura'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AsaasWebhookListView(APIView):
    """
    View para listar webhooks processados
    """
    permission_classes = []  # Não exige autenticação para debug
    
    def get(self, request):
        """
        Lista webhooks processados
        """
        try:
            webhooks = AsaasWebhook.objects.all()[:50]  # Últimos 50
            
            webhook_list = []
            for webhook in webhooks:
                webhook_list.append({
                    'id': webhook.id,
                    'event_type': webhook.event_type,
                    'asaas_id': webhook.asaas_id,
                    'status': webhook.status,
                    'created_at': webhook.created_at.isoformat(),
                    'processed_at': webhook.processed_at.isoformat() if webhook.processed_at else None,
                    'error_message': webhook.error_message
                })
            
            return Response({
                'webhooks': webhook_list,
                'total': len(webhook_list)
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Erro ao listar webhooks: {str(e)}")
            return Response(
                {'error': 'Erro ao listar webhooks'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AsaasPaymentsView(APIView):
    """
    Lista pagamentos (cobranças) do cliente no Asaas e retorna num formato
    próprio para o frontend de histórico de pagamentos.
    """
    permission_classes = [IsAuthenticated]
    def get(self, request):
        try:
            empresa = getattr(request.user, 'empresa_atual', None)
            if not empresa:
                return Response({'error': 'Empresa não encontrada'}, status=status.HTTP_404_NOT_FOUND)
            if not empresa.asaas_customer_id:
                return Response({'payments': [], 'total': 0})

            # Parâmetros de paginação
            offset = int(request.query_params.get('offset', 0))
            limit = min(int(request.query_params.get('limit', 20)), 100)  # Máximo 100 por vez

            asaas = AsaasService()
            raw = asaas.list_customer_payments(empresa.asaas_customer_id, limit=limit, offset=offset)
            items = raw.get('data', []) if isinstance(raw, dict) else []

            def _format_payment(p):
                status_map = {
                    'RECEIVED': 'Pago',
                    'CONFIRMED': 'Pago',
                    'PENDING': 'Pendente',
                    'OVERDUE': 'Atrasado',
                    'CANCELLED': 'Cancelado',
                    'REFUNDED': 'Estornado',
                }
                desc = p.get('description') or 'Assinatura'
                method = (p.get('billingType') or '').replace('_', ' ').title()
                invoice_number = p.get('invoiceNumber') or p.get('id')
                due_date = p.get('dueDate')
                paid_date = p.get('confirmedDate') or p.get('paymentDate')
                amount = float(p.get('value') or 0)
                status_label = status_map.get(str(p.get('status')).upper(), str(p.get('status')).title())
                return {
                    'id': p.get('id'),
                    'date': p.get('dateCreated') or due_date,
                    'description': desc,
                    'amount': amount,
                    'status': status_label,
                    'invoiceNumber': invoice_number,
                    'paymentMethod': method,
                    'dueDate': due_date,
                    'paidDate': paid_date,
                    'invoiceUrl': p.get('invoiceUrl'),
                    'bankSlipUrl': p.get('bankSlipUrl'),
                    'canDownloadInvoice': bool(p.get('invoiceUrl')),
                }

            payments = [_format_payment(p) for p in items]
            return Response({'payments': payments, 'total': len(payments)}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Erro ao listar pagamentos: {str(e)}")
            return Response({'error': 'Erro ao listar pagamentos'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AsaasPaymentInvoiceView(APIView):
    """
    Retorna URL de nota fiscal/recibo do pagamento, se disponível no Asaas.
    Observação: Asaas não gera NF-e por padrão. O usual é invoiceUrl/bankSlipUrl.
    Se houver integração fiscal, retornaríamos o link da NF-e aqui.
    """
    permission_classes = [IsAuthenticated]
    def get(self, request, payment_id: str):
        try:
            asaas = AsaasService()
            data = asaas.get_payment(payment_id)
            # Preferência: invoiceUrl; fallback: bankSlipUrl
            url = data.get('invoiceUrl') or data.get('bankSlipUrl')
            if not url:
                return Response({'error': 'Sem documento para download'}, status=status.HTTP_404_NOT_FOUND)
            return Response({'url': url})
        except Exception as e:
            logger.error(f"Erro ao obter invoice do pagamento {payment_id}: {str(e)}")
            return Response({'error': 'Erro ao obter invoice'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AsaasSimulateSubscriptionView(APIView):
    """
    View para simular criação de assinatura (para testes)
    """
    permission_classes = []  # Não exige autenticação para testes
    
    def post(self, request):
        """
        Simula a criação de uma assinatura no Asaas
        """
        try:
            empresa_id = request.data.get('empresa_id')
            plano_id = request.data.get('plano_id')
            
            if not empresa_id or not plano_id:
                return Response(
                    {'error': 'empresa_id e plano_id são obrigatórios'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            from empresas.models import Empresa
            from assinaturas.models import Plano
            
            empresa = Empresa.objects.get(id=empresa_id)
            plano = Plano.objects.get(id=plano_id)
            
            asaas_service = AsaasService()
            
            # Cria cliente se não existir
            if not empresa.asaas_customer_id:
                customer_data = asaas_service.create_customer(empresa)
                logger.info(f"Cliente criado no Asaas: {customer_data.get('id')}")
            
            # Calcula dias restantes, se existir assinatura ativa (para renovação antecipada)
            dias_restantes = 0
            try:
                assinatura_ativa = getattr(empresa, 'assinatura_ativa', None)
            except Exception:
                assinatura_ativa = None
            # Somamos dias restantes apenas se a renovação for para o MESMO plano
            if (
                assinatura_ativa 
                and not assinatura_ativa.expirada 
                and assinatura_ativa.plano_id == plano.id
            ):
                from django.utils import timezone as _tz
                dias_restantes = max((assinatura_ativa.fim.date() - _tz.now().date()).days, 0)
            
            # Cria reserva de pagamento (NÃO cria assinatura no Asaas ainda)
            reservation_data = asaas_service.create_payment_reservation(empresa, plano, extra_days=dias_restantes)
            
            logger.info(f"Reserva de pagamento criada: {reservation_data}")
            
            return Response({
                'success': True,
                'payment_id': reservation_data.get('payment_id'),
                'customer_id': empresa.asaas_customer_id,
                'assinatura_id': reservation_data.get('assinatura_id'),
                'payment_link': reservation_data.get('payment_link'),
                'message': 'Reserva de pagamento criada com sucesso',
                'details': {
                    'empresa': empresa.nome_fantasia or empresa.razao_social,
                    'plano': plano.nome,
                    'valor': plano.preco,
                    'trial_days': plano.trial_days,
                    'status': 'PENDING'
                }
            }, status=status.HTTP_201_CREATED)
            
        except (Empresa.DoesNotExist, Plano.DoesNotExist):
            return Response(
                {'error': 'Empresa ou plano não encontrado'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Erro ao simular assinatura no Asaas: {str(e)}")
            return Response(
                {'error': f'Erro ao simular assinatura: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
