import requests
import logging
import time
from typing import Dict, Any, Optional
from django.conf import settings
from django.utils import timezone
from zoneinfo import ZoneInfo
from dateutil.relativedelta import relativedelta
from empresas.models import Empresa
from assinaturas.models import Assinatura, Plano

logger = logging.getLogger(__name__)


class AsaasService:
    """
    Serviço para integração com a API do Asaas
    """
    
    def __init__(self):
        self.api_key = settings.ASAAS_API_KEY
        self.api_url = settings.ASAAS_API_URL
        self.headers = {
            'access_token': self.api_key,
            'Content-Type': 'application/json'
        }
        # Timezone local usado para cálculo de datas de ciclo/vencimento
        self.local_tz = ZoneInfo(getattr(settings, 'LOCAL_TIME_ZONE', 'America/Sao_Paulo'))
    
    def _make_request(self, method: str, endpoint: str, data: Dict = None) -> Dict[str, Any]:
        """
        Faz uma requisição para a API do Asaas
        """
        url = f"{self.api_url}/{endpoint}"
        
        try:
            if method.upper() == 'GET':
                response = requests.get(url, headers=self.headers)
            elif method.upper() == 'POST':
                response = requests.post(url, headers=self.headers, json=data)
            elif method.upper() == 'PUT':
                response = requests.put(url, headers=self.headers, json=data)
            elif method.upper() == 'DELETE':
                response = requests.delete(url, headers=self.headers)
            else:
                raise ValueError(f"Método HTTP não suportado: {method}")
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro na requisição para Asaas: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response content: {e.response.text}")
            raise
    
    def create_customer(self, empresa: Empresa) -> Dict[str, Any]:
        """
        Cria um cliente no Asaas
        """
        customer_data = {
            'name': empresa.nome_fantasia or empresa.razao_social,
            'email': empresa.email_comercial,
            'phone': empresa.telefone1,
            'mobilePhone': empresa.telefone2,
            'cpfCnpj': empresa.cnpj or empresa.cpf,
            'postalCode': empresa.endereco.cep if hasattr(empresa, 'endereco') else None,
            'address': empresa.endereco.endereco if hasattr(empresa, 'endereco') else None,
            'addressNumber': empresa.endereco.numero if hasattr(empresa, 'endereco') else None,
            'complement': empresa.endereco.complemento if hasattr(empresa, 'endereco') else None,
            'province': empresa.endereco.bairro if hasattr(empresa, 'endereco') else None,
            'city': empresa.endereco.cidade if hasattr(empresa, 'endereco') else None,
            'state': empresa.endereco.estado if hasattr(empresa, 'endereco') else None,
        }
        
        # Remove campos None
        customer_data = {k: v for k, v in customer_data.items() if v is not None}
        
        response = self._make_request('POST', 'customers', customer_data)
        
        # Salva o ID do cliente na empresa
        empresa.asaas_customer_id = response.get('id')
        empresa.save(update_fields=['asaas_customer_id'])
        
        return response
    
    def create_subscription(self, empresa: Empresa, plano: Plano, extra_days: int = 0, due_date_override: Optional[str] = None) -> Dict[str, Any]:
        """
        Cria uma assinatura no Asaas.
        Caso extra_days > 0, esses dias serão adicionados à duração padrão do plano
        para compensar dias restantes de uma assinatura atual (renovação antecipada).
        """
        if not empresa.asaas_customer_id:
            # Cria o cliente primeiro se não existir
            self.create_customer(empresa)
        
        # Cancela assinaturas pendentes da empresa antes de criar nova
        from assinaturas.models import Assinatura
        assinaturas_pendentes = Assinatura.objects.filter(
            empresa=empresa,
            payment_status='PENDING',
            ativa=False
        )
        
        for assinatura_pendente in assinaturas_pendentes:
            try:
                # Importante: NÃO deletar no Asaas antes de pagamento confirmado.
                # Apenas marcamos como cancelada no nosso sistema para evitar concorrência.
                assinatura_pendente.payment_status = 'CANCELLED'
                assinatura_pendente.ativa = False
                assinatura_pendente.expirada = True
                assinatura_pendente.save(update_fields=['payment_status', 'ativa', 'expirada'])
                logger.info(f"Assinatura pendente marcada como cancelada localmente: {assinatura_pendente.id}")
            except Exception as e:
                logger.error(f"Erro ao cancelar (local) assinatura pendente {assinatura_pendente.id}: {str(e)}")
        
        from datetime import timedelta, time, datetime
        # Se due_date_override for informado, usa-o diretamente
        if due_date_override:
            due_date_date = datetime.strptime(due_date_override, '%Y-%m-%d').date()
        else:
            # Calcula com base em mês calendário quando apropriado
            total_extra_days = max(extra_days, 0)
            base_now = timezone.now().astimezone(self.local_tz)
            if plano.duracao_dias % 30 == 0:
                months = max(plano.duracao_dias // 30, 1)
                due_date_dt = base_now + relativedelta(months=months) + timedelta(days=total_extra_days)
                due_date_date = due_date_dt.date()
            else:
                dias_totais = max(plano.duracao_dias + total_extra_days, 0)
                due_date_date = (base_now + timedelta(days=dias_totais)).date()

        # Salva como aware na timezone local para evitar drift de data
        due_date = timezone.make_aware(datetime.combine(due_date_date, time(hour=12)), self.local_tz)
        next_due_date = due_date.strftime('%Y-%m-%d')
        
        subscription_data = {
            'customer': empresa.asaas_customer_id,
            'billingType': 'UNDEFINED',
            'value': float(plano.preco),
            'nextDueDate': next_due_date,
            'cycle': 'MONTHLY',
            'description': f"Plano {plano.nome} - {empresa.nome_fantasia or empresa.razao_social}",
            'endDate': next_due_date,  # define data de fim com base na duração do plano
            'fine': {
                'value': 2.00
            },
            'interest': {
                'value': 1.00
            },
            'discount': {
                'value': 0,
                'dueDateLimitDays': 0
            }
        }
        
        response = self._make_request('POST', 'subscriptions', subscription_data)
        
        # Cria a assinatura no nosso sistema
        assinatura = Assinatura.objects.create(
            empresa=empresa,
            plano=plano,
            asaas_subscription_id=response.get('id'),
            asaas_customer_id=empresa.asaas_customer_id,
            payment_status='PENDING',
            trial_end_date=None,
            fim=due_date,
            next_payment_date=next_due_date,
            ativa=False,
            expirada=False
        )
        
        return response

    def create_payment_reservation(self, empresa: Empresa, plano: Plano, extra_days: int = 0, due_date_override: Optional[str] = None) -> Dict[str, Any]:
        """
        Cria apenas uma reserva de pagamento no nosso sistema, SEM criar assinatura no Asaas.
        A assinatura no Asaas só será criada quando o pagamento for confirmado.
        """
        if not empresa.asaas_customer_id:
            # Cria o cliente primeiro se não existir
            self.create_customer(empresa)
        
        # Cancela assinaturas pendentes da empresa antes de criar nova
        from assinaturas.models import Assinatura
        assinaturas_pendentes = Assinatura.objects.filter(
            empresa=empresa,
            payment_status='PENDING',
            ativa=False
        )
        
        for assinatura_pendente in assinaturas_pendentes:
            try:
                # NÃO deletar no Asaas antes do pagamento.
                assinatura_pendente.payment_status = 'CANCELLED'
                assinatura_pendente.ativa = False
                assinatura_pendente.expirada = True
                assinatura_pendente.save(update_fields=['payment_status', 'ativa', 'expirada'])
                logger.info(f"Assinatura pendente marcada como cancelada localmente: {assinatura_pendente.id}")
            except Exception as e:
                logger.error(f"Erro ao cancelar (local) assinatura pendente {assinatura_pendente.id}: {str(e)}")
        
        from datetime import timedelta, time, datetime
        # Se due_date_override for informado, usa-o diretamente
        if due_date_override:
            due_date_date = datetime.strptime(due_date_override, '%Y-%m-%d').date()
        else:
            # Calcula com base em mês calendário quando apropriado
            total_extra_days = max(extra_days, 0)
            base_now = timezone.now().astimezone(self.local_tz)
            if plano.duracao_dias % 30 == 0:
                months = max(plano.duracao_dias // 30, 1)
                due_date_dt = base_now + relativedelta(months=months) + timedelta(days=total_extra_days)
                due_date_date = due_date_dt.date()
            else:
                dias_totais = max(plano.duracao_dias + total_extra_days, 0)
                due_date_date = (base_now + timedelta(days=dias_totais)).date()

        # Salva como aware na timezone local
        due_date = timezone.make_aware(datetime.combine(due_date_date, time(hour=12)), self.local_tz)
        next_due_date = due_date.strftime('%Y-%m-%d')
        
        # Cria apenas uma cobrança simples no Asaas (não uma assinatura)
        payment_data = {
            'customer': empresa.asaas_customer_id,
            'billingType': 'UNDEFINED',
            'value': float(plano.preco),
            'dueDate': next_due_date,
            'description': f"Plano {plano.nome} - {empresa.nome_fantasia or empresa.razao_social}",
            'externalReference': f'RESERVATION_{empresa.id}_{plano.id}'
        }
        
        # Cria cobrança no Asaas
        payment_response = self._make_request('POST', 'payments', payment_data)
        
        # Cria a assinatura no nosso sistema (sem asaas_subscription_id ainda)
        assinatura = Assinatura.objects.create(
            empresa=empresa,
            plano=plano,
            asaas_subscription_id=None,  # Será preenchido quando pagamento for confirmado
            asaas_customer_id=empresa.asaas_customer_id,
            payment_status='PENDING',
            trial_end_date=None,
            fim=due_date,
            next_payment_date=next_due_date,
            ativa=False,
            expirada=False
        )
        
        # Salva o ID do pagamento na assinatura para referência
        assinatura.observacoes = f"Payment ID: {payment_response.get('id')}"
        assinatura.save(update_fields=['observacoes'])
        
        return {
            'payment_id': payment_response.get('id'),
            'payment_link': payment_response.get('invoiceUrl') or payment_response.get('bankSlipUrl'),
            'assinatura_id': assinatura.id,
            'empresa_id': empresa.id,
            'plano_id': plano.id
        }

    def ensure_single_active_subscription(self, empresa: Empresa, nova_assinatura: Assinatura = None):
        """
        Garante que apenas uma assinatura fique ativa por empresa.
        Se nova_assinatura for fornecida, ela será a única ativa.
        """
        from assinaturas.models import Assinatura
        
        # Busca todas as assinaturas ativas da empresa
        assinaturas_ativas = Assinatura.objects.filter(
            empresa=empresa,
            ativa=True
        )
        
        # Se há mais de uma assinatura ativa, mantém apenas a mais recente
        if assinaturas_ativas.count() > 1:
            assinatura_mais_recente = assinaturas_ativas.order_by('-criado_em').first()
            
            # Cancela as outras assinaturas ativas
            for assinatura in assinaturas_ativas.exclude(id=assinatura_mais_recente.id):
                assinatura.payment_status = 'CANCELLED'
                assinatura.ativa = False
                assinatura.expirada = True
                assinatura.save(update_fields=['payment_status', 'ativa', 'expirada'])
                
                # Cancela no Asaas se tiver ID
                if assinatura.asaas_subscription_id:
                    try:
                        self._make_request('DELETE', f'subscriptions/{assinatura.asaas_subscription_id}')
                        logger.info(f"Assinatura cancelada no Asaas: {assinatura.asaas_subscription_id}")
                    except Exception as e:
                        logger.error(f"Erro ao cancelar assinatura no Asaas: {str(e)}")
                
                logger.info(f"Assinatura duplicada cancelada: {assinatura.id}")
        
        # Se nova_assinatura foi fornecida, garante que ela seja a única ativa
        if nova_assinatura:
            # Cancela todas as outras assinaturas ativas
            outras_ativas_qs = Assinatura.objects.filter(
                empresa=empresa,
                ativa=True
            ).exclude(id=nova_assinatura.id)

            # Cancela no Asaas também
            for assinatura in outras_ativas_qs:
                if assinatura.asaas_subscription_id:
                    try:
                        self._make_request('DELETE', f'subscriptions/{assinatura.asaas_subscription_id}')
                        logger.info(f"Assinatura (outra ativa) cancelada no Asaas: {assinatura.asaas_subscription_id}")
                    except Exception as e:
                        logger.error(f"Erro ao cancelar assinatura no Asaas: {str(e)}")
            outras_ativas_qs.update(
                payment_status='CANCELLED',
                ativa=False,
                expirada=True
            )
            
            # Ativa a nova assinatura
            nova_assinatura.ativa = True
            nova_assinatura.expirada = False
            nova_assinatura.save(update_fields=['ativa', 'expirada'])

    def create_payment_link(self, subscription_id: str) -> str:
        """
        Cria um link de pagamento real no Asaas
        """
        try:
            # Obtém dados da assinatura
            subscription_data = self._make_request('GET', f'subscriptions/{subscription_id}')
            logger.info(f"Dados da assinatura: {subscription_data}")
            
            # Obtém dados do cliente
            customer_id = subscription_data.get('customer')
            customer_data = self._make_request('GET', f'customers/{customer_id}')
            logger.info(f"Dados do cliente: {customer_data}")
            
            # Cria uma cobrança simples
            # Usa a duração do plano para calcular a data de vencimento
            assinatura = Assinatura.objects.get(asaas_subscription_id=subscription_id)
            # Usa sempre a data salva na assinatura para garantir consistência
            # Ajuste: se por algum motivo a data salva for +1, normalizamos subtraindo 1 dia
            from datetime import timedelta
            if assinatura.next_payment_date:
                adjusted_date = assinatura.next_payment_date
            else:
                adjusted_date = assinatura.fim.date()
            # Normaliza para evitar 31 quando ciclo é 30
            due_date = (adjusted_date).strftime('%Y-%m-%d')
            payment_data = {
                'customer': customer_id,
                'billingType': 'UNDEFINED',
                'value': subscription_data.get('value'),
                'dueDate': due_date,
                'description': subscription_data.get('description', 'Pagamento de assinatura'),
                'externalReference': subscription_id
            }
            
            # Remove campos None
            payment_data = {k: v for k, v in payment_data.items() if v is not None}
            
            logger.info(f"Dados do pagamento: {payment_data}")
            
            # Cria a cobrança
            payment_response = self._make_request('POST', 'payments', payment_data)
            logger.info(f"Resposta da cobrança: {payment_response}")
            
            # Gera link de pagamento
            payment_id = payment_response.get('id')
            if payment_id:
                # Aguarda um pouco para garantir que a cobrança foi criada
                time.sleep(3)
                
                # Verifica se a cobrança existe
                try:
                    payment_check = self._make_request('GET', f'payments/{payment_id}')
                    logger.info(f"Verificação da cobrança: {payment_check}")
                    
                    # Usa o invoiceUrl se disponível, senão cria o link manualmente
                    invoice_url = payment_check.get('invoiceUrl')
                    if invoice_url:
                        logger.info(f"Link de pagamento (invoiceUrl): {invoice_url}")
                        return invoice_url
                    else:
                        # Cria link manual para sandbox
                        return f"https://sandbox.asaas.com/subscriptions/{subscription_id}"
                        
                except Exception as e:
                    logger.error(f"Erro ao verificar cobrança: {str(e)}")
                    return f"https://sandbox.asaas.com/subscriptions/{subscription_id}"
            else:
                logger.error("ID da cobrança não encontrado na resposta")
                return f"https://sandbox.asaas.com/subscriptions/{subscription_id}"
                
        except Exception as e:
            logger.error(f"Erro ao criar link de pagamento: {str(e)}")
            return f"https://sandbox.asaas.com/subscriptions/{subscription_id}"

    def get_payment_link(self, subscription_id: str) -> str:
        """
        Obtém o link de pagamento de uma assinatura
        """
        try:
            # Tenta criar um novo link de pagamento
            payment_link = self.create_payment_link(subscription_id)
            
            # Se não conseguiu criar, retorna link padrão do sandbox
            if not payment_link or 'sandbox.asaas.com/subscriptions/' in payment_link:
                # Tenta obter dados da assinatura para criar cobrança
                try:
                    subscription_data = self._make_request('GET', f'subscriptions/{subscription_id}')
                    
                    # Usa a duração do plano para calcular a data de vencimento
                    assinatura = Assinatura.objects.get(asaas_subscription_id=subscription_id)
                    # Usa sempre a data salva na assinatura para garantir consistência
                    from datetime import timedelta
                    if assinatura.next_payment_date:
                        adjusted_date = assinatura.next_payment_date
                    else:
                        adjusted_date = assinatura.fim.date()
                    due_date = (adjusted_date).strftime('%Y-%m-%d')
                    payment_data = {
                        'customer': subscription_data.get('customer'),
                        'billingType': 'UNDEFINED',
                        'value': subscription_data.get('value'),
                        'dueDate': due_date,
                        'description': f"Pagamento - {subscription_data.get('description', 'Assinatura')}",
                        'externalReference': subscription_id
                    }
                    
                    payment_response = self._make_request('POST', 'payments', payment_data)
                    payment_id = payment_response.get('id')
                    
                    if payment_id:
                        return f"https://sandbox.asaas.com/payments/{payment_id}"
                    else:
                        return f"https://sandbox.asaas.com/subscriptions/{subscription_id}"
                        
                except Exception as e:
                    logger.error(f"Erro ao obter dados da assinatura: {str(e)}")
                    return f"https://sandbox.asaas.com/subscriptions/{subscription_id}"
            else:
                return payment_link
                
        except Exception as e:
            logger.error(f"Erro ao obter link de pagamento: {str(e)}")
            return f"https://sandbox.asaas.com/subscriptions/{subscription_id}"

    def create_simple_payment(self, customer_id: str, value: float, description: str, due_date: Optional[str] = None, external_reference: Optional[str] = None) -> Dict[str, Any]:
        """
        Cria uma cobrança simples (one-time payment) no Asaas para valores avulsos,
        como a diferença de upgrade de plano.
        """
        if due_date is None:
            due_date = timezone.now().date().strftime('%Y-%m-%d')

        payment_data = {
            'customer': customer_id,
            'billingType': 'UNDEFINED',
            'value': float(value),
            'dueDate': due_date,
            'description': description,
        }

        if external_reference:
            payment_data['externalReference'] = external_reference

        # Remove campos None
        payment_data = {k: v for k, v in payment_data.items() if v is not None}

        return self._make_request('POST', 'payments', payment_data)

    def create_product(self, plano: Plano) -> Dict[str, Any]:
        """
        Cria um produto no Asaas
        """
        product_data = {
            'name': plano.nome,
            'description': f"Plano {plano.nome} - SmartStrategy",
            'price': float(plano.preco)
        }
        
        response = self._make_request('POST', 'products', product_data)
        
        # Salva o ID do produto no plano
        plano.asaas_product_id = response.get('id')
        plano.save(update_fields=['asaas_product_id'])
        
        return response

    def cancel_subscription(self, assinatura: Assinatura) -> Dict[str, Any]:
        """
        Cancela uma assinatura no Asaas
        """
        if not assinatura.asaas_subscription_id:
            raise ValueError("Assinatura não possui ID do Asaas")
        
        response = self._make_request('DELETE', f'subscriptions/{assinatura.asaas_subscription_id}')
        return response

    def get_subscription_status(self, asaas_subscription_id: str) -> Dict[str, Any]:
        """
        Obtém o status de uma assinatura no Asaas
        """
        return self._make_request('GET', f'subscriptions/{asaas_subscription_id}')

    def list_customer_subscriptions(self, asaas_customer_id: str) -> Dict[str, Any]:
        """Lista assinaturas de um cliente no Asaas."""
        return self._make_request('GET', f'subscriptions?customer={asaas_customer_id}')

    def list_customer_payments(self, asaas_customer_id: str, limit: int = 100, offset: int = 0, status_filter: Optional[str] = None) -> Dict[str, Any]:
        """
        Lista cobranças (payments) do cliente no Asaas, mais recente primeiro.
        status_filter pode ser: PENDING, CONFIRMED, RECEIVED, OVERDUE, etc.
        """
        params = [f"customer={asaas_customer_id}", f"limit={max(1, min(limit, 100))}", f"offset={offset}", "orderBy=dueDate", "sort=DESC"]
        if status_filter:
            params.append(f"status={status_filter}")
        query = "&".join(params)
        return self._make_request('GET', f'payments?{query}')

    def get_payment(self, payment_id: str) -> Dict[str, Any]:
        """Obtém os detalhes de uma cobrança (payment) no Asaas."""
        return self._make_request('GET', f'payments/{payment_id}')

    def process_webhook(self, payload: Dict[str, Any]) -> bool:
        """
        Processa webhook recebido do Asaas
        """
        from .models import AsaasWebhook

        def _extract_event_id(data: Dict[str, Any]) -> str:
            try:
                if 'subscription' in data and isinstance(data['subscription'], dict):
                    return data['subscription'].get('id') or 'unknown'
                if 'payment' in data and isinstance(data['payment'], dict):
                    return data['payment'].get('id') or 'unknown'
                return data.get('id') or 'unknown'
            except Exception:
                return 'unknown'
        
        # Cria registro do webhook
        webhook = AsaasWebhook.objects.create(
            event_type=payload.get('event'),
            asaas_id=_extract_event_id(payload),
            payload=payload,
            status='pending'
        )
        
        try:
            event_type = payload.get('event')
            
            if event_type == 'SUBSCRIPTION_CREATED':
                self._handle_subscription_created(payload)
            elif event_type == 'SUBSCRIPTION_ACTIVATED':
                self._handle_subscription_activated(payload)
            elif event_type == 'SUBSCRIPTION_CANCELLED':
                self._handle_subscription_cancelled(payload)
            elif event_type == 'SUBSCRIPTION_INACTIVATED':
                self._handle_subscription_cancelled(payload)
            elif event_type == 'SUBSCRIPTION_DELETED':
                self._handle_subscription_cancelled(payload)
            elif event_type == 'PAYMENT_RECEIVED':
                self._handle_payment_received(payload)
            elif event_type == 'PAYMENT_CONFIRMED':
                # Tratar como recebido/confirmado
                self._handle_payment_received(payload)
            elif event_type == 'PAYMENT_OVERDUE':
                self._handle_payment_overdue(payload)
            else:
                logger.info(f"Evento não processado: {event_type}")
            
            # Marca como processado
            webhook.mark_as_processed()
            return True
            
        except Exception as e:
            logger.error(f"Erro ao processar webhook: {str(e)}")
            if 'webhook' in locals():
                webhook.mark_as_failed(str(e))
            return False
    
    def _handle_subscription_created(self, payload: Dict[str, Any]):
        """Processa evento de assinatura criada"""
        subscription_data = payload.get('subscription', {})
        customer_id = subscription_data.get('customer')
        
        # Encontra a empresa pelo customer_id
        try:
            empresa = Empresa.objects.get(asaas_customer_id=customer_id)
            # Busca a assinatura mais recente com esse ID
            assinatura = Assinatura.objects.filter(
                asaas_subscription_id=subscription_data.get('id')
            ).order_by('-criado_em').first()
            
            if assinatura:
                # Sempre deixa como PENDING até o pagamento ser confirmado
                assinatura.payment_status = 'PENDING'
                assinatura.ativa = False
                assinatura.save(update_fields=['payment_status', 'ativa'])

                # Se a assinatura foi criada no Asaas manualmente (não existente localmente),
                # garantimos que haverá desbloqueio quando ativar/confirmar. Para reforço,
                # se já existe outra assinatura ativa do mesmo cliente, desbloqueia.
                try:
                    subs = self.list_customer_subscriptions(customer_id)
                    has_active_remote = any((s.get('status') in ('ACTIVE', 'RECEIVED', 'CONFIRMED')) for s in subs.get('data', []) if s.get('id') != assinatura.asaas_subscription_id)
                    if has_active_remote:
                        empresa.ativo = True
                        empresa.save(update_fields=['ativo'])
                except Exception:
                    pass
                
                logger.info(f"Assinatura criada para empresa {empresa.nome_fantasia} - aguardando pagamento")
            else:
                logger.warning(f"Assinatura não encontrada para subscription_id: {subscription_data.get('id')}")
            
        except Empresa.DoesNotExist as e:
            logger.error(f"Empresa não encontrada: {str(e)}")
        except Exception as e:
            logger.error(f"Erro ao processar subscription_created: {str(e)}")
    
    def _handle_subscription_activated(self, payload: Dict[str, Any]):
        """Processa evento de assinatura ativada"""
        subscription_data = payload.get('subscription', {})
        
        try:
            # Busca a assinatura mais recente com esse ID
            assinatura = Assinatura.objects.filter(
                asaas_subscription_id=subscription_data.get('id')
            ).order_by('-criado_em').first()
            
            if assinatura:
                assinatura.payment_status = 'CONFIRMED'
                assinatura.ativa = True
                assinatura.save(update_fields=['payment_status', 'ativa'])
                # Desbloqueia empresa
                empresa = assinatura.empresa
                if not empresa.ativo:
                    empresa.ativo = True
                    empresa.save(update_fields=['ativo'])
                # Histórico e notificação
                try:
                    from assinaturas.models import HistoricoPagamento
                    HistoricoPagamento.objects.create(
                        assinatura=assinatura,
                        tipo='ATIVACAO',
                        descricao=f'Assinatura ativada via webhook Asaas ({subscription_data.get("id")})',
                        valor_novo=assinatura.plano.preco
                    )
                    from painel_admin.notificacoes_utils import criar_notificacao_empresa_ativada, criar_notificacao_pagamento_recebido
                    criar_notificacao_empresa_ativada(empresa, assinatura.plano.nome)
                    criar_notificacao_pagamento_recebido(assinatura, assinatura.plano.preco, 'Pagamento (assinatura ativada)')
                except Exception as _:
                    pass
                
                # Ao ativar a nova, cancela no Asaas e localmente quaisquer outras assinaturas da mesma empresa
                outras_ativas = Assinatura.objects.filter(
                    empresa=assinatura.empresa,
                    ativa=True
                ).exclude(id=assinatura.id)
                for antiga in outras_ativas:
                    if antiga.asaas_subscription_id:
                        try:
                            self._make_request('DELETE', f'subscriptions/{antiga.asaas_subscription_id}')
                            logger.info(f"Assinatura anterior cancelada no Asaas após ativação da nova: {antiga.asaas_subscription_id}")
                        except Exception as e:
                            logger.error(f"Erro ao cancelar assinatura anterior no Asaas: {str(e)}")
                    antiga.payment_status = 'CANCELLED'
                    antiga.ativa = False
                    antiga.expirada = True
                    antiga.save(update_fields=['payment_status', 'ativa', 'expirada'])

                # Garante empresa desbloqueada ao final
                if not empresa.ativo:
                    empresa.ativo = True
                    empresa.save(update_fields=['ativo'])

                logger.info(f"Assinatura ativada: {assinatura}")
            else:
                logger.warning(f"Assinatura não encontrada para subscription_id: {subscription_data.get('id')}")
            
        except Exception as e:
            logger.error(f"Erro ao processar subscription_activated: {str(e)}")
    
    def _handle_subscription_cancelled(self, payload: Dict[str, Any]):
        """Processa evento de assinatura cancelada"""
        subscription_data = payload.get('subscription', {})
        
        try:
            # Busca a assinatura mais recente com esse ID
            assinatura = Assinatura.objects.filter(
                asaas_subscription_id=subscription_data.get('id')
            ).order_by('-criado_em').first()
            
            if assinatura:
                assinatura.payment_status = 'CANCELLED'
                assinatura.ativa = False
                assinatura.expirada = True
                assinatura.save(update_fields=['payment_status', 'ativa', 'expirada'])
                # Bloqueia empresa
                empresa = assinatura.empresa
                if empresa.ativo:
                    empresa.ativo = False
                    empresa.save(update_fields=['ativo'])
                # Histórico e notificação
                try:
                    from assinaturas.models import HistoricoPagamento
                    HistoricoPagamento.objects.create(
                        assinatura=assinatura,
                        tipo='CANCELAMENTO',
                        descricao=f'Assinatura cancelada no Asaas ({subscription_data.get("id")})',
                        valor_anterior=assinatura.plano.preco
                    )
                    from painel_admin.notificacoes_utils import criar_notificacao_empresa_bloqueada
                    criar_notificacao_empresa_bloqueada(empresa, 'Assinatura cancelada no Asaas')
                except Exception as _:
                    pass
                
                logger.info(f"Assinatura cancelada: {assinatura}")
            else:
                logger.warning(f"Assinatura não encontrada para subscription_id: {subscription_data.get('id')}")
            
        except Exception as e:
            logger.error(f"Erro ao processar subscription_cancelled: {str(e)}")
    
    def _handle_payment_received(self, payload: Dict[str, Any]):
        """Processa evento de pagamento recebido"""
        payment_data = payload.get('payment', {})
        external_reference = payment_data.get('externalReference')
        
        logger.info(f"PAYMENT_RECEIVED - externalReference: {external_reference}")
        logger.info(f"PAYMENT_RECEIVED - payment_data: {payment_data}")
        
        # Verifica se é pagamento de upgrade (começa com UPGRADE_)
        if external_reference and external_reference.startswith('UPGRADE_'):
            try:
                # Extrai o ID da assinatura do externalReference
                assinatura_id = external_reference.replace('UPGRADE_', '')
                assinatura = Assinatura.objects.get(id=assinatura_id)
                
                logger.info(f"Processando upgrade para assinatura {assinatura.id}")
                
                # Busca a nova assinatura criada durante o upgrade
                # Pode estar com status PENDING ou CONFIRMED
                nova_assinatura = Assinatura.objects.filter(
                    empresa=assinatura.empresa,
                    plano__id__gt=assinatura.plano.id,  # Plano superior
                    criado_em__gt=assinatura.criado_em  # Criada depois
                ).order_by('-criado_em').first()
                
                if not nova_assinatura:
                    # Tenta buscar por assinatura pendente
                    nova_assinatura = Assinatura.objects.filter(
                        empresa=assinatura.empresa,
                        ativa=False,
                        payment_status='PENDING'
                    ).order_by('-criado_em').first()
                
                if nova_assinatura:
                    logger.info(f"Nova assinatura encontrada: {nova_assinatura.id}, plano: {nova_assinatura.plano.nome}")
                    
                    # Cria a assinatura no Asaas agora que o pagamento foi confirmado
                    # Garante que o nextDueDate da assinatura fique igual ao fim do ciclo atual
                    override_date = None
                    try:
                        override_date = nova_assinatura.fim.date().strftime('%Y-%m-%d') if nova_assinatura.fim else None
                    except Exception:
                        override_date = None
                    subscription_response = self.create_subscription(
                        nova_assinatura.empresa,
                        nova_assinatura.plano,
                        extra_days=0,
                        due_date_override=override_date
                    )
                    logger.info(f"Assinatura criada no Asaas: {subscription_response}")
                    
                    # Atualiza a nova assinatura com o ID do Asaas
                    nova_assinatura.asaas_subscription_id = subscription_response.get('id')
                    nova_assinatura.payment_status = 'CONFIRMED'
                    nova_assinatura.save(update_fields=['asaas_subscription_id', 'payment_status'])
                    
                    # Pagamento confirmado do upgrade e nova assinatura criada com sucesso
                    # Agora podemos cancelar a assinatura antiga no Asaas imediatamente
                    if assinatura.asaas_subscription_id:
                        try:
                            self._make_request('DELETE', f'subscriptions/{assinatura.asaas_subscription_id}')
                            logger.info(f"Assinatura antiga cancelada no Asaas após pagamento do upgrade: {assinatura.asaas_subscription_id}")
                        except Exception as e:
                            logger.error(f"Erro ao cancelar assinatura antiga no Asaas: {str(e)}")
                    
                    # E marcamos a antiga como cancelada localmente
                    assinatura.payment_status = 'CANCELLED'
                    assinatura.ativa = False
                    assinatura.expirada = True
                    assinatura.save(update_fields=['payment_status', 'ativa', 'expirada'])
                    
                    # Garante que apenas uma assinatura fique ativa
                    self.ensure_single_active_subscription(assinatura.empresa, nova_assinatura)
                    # Desbloqueia empresa e cria histórico/notificação
                    try:
                        empresa = nova_assinatura.empresa
                        if not empresa.ativo:
                            empresa.ativo = True
                            empresa.save(update_fields=['ativo'])
                        from assinaturas.models import HistoricoPagamento
                        HistoricoPagamento.objects.create(
                            assinatura=nova_assinatura,
                            tipo='ATIVACAO',
                            descricao='Upgrade confirmado via Asaas',
                            valor_novo=nova_assinatura.plano.preco
                        )
                        from painel_admin.notificacoes_utils import criar_notificacao_empresa_ativada, criar_notificacao_pagamento_recebido
                        criar_notificacao_empresa_ativada(empresa, nova_assinatura.plano.nome)
                        valor = payment_data.get('value') or float(nova_assinatura.plano.preco)
                        criar_notificacao_pagamento_recebido(nova_assinatura, valor, 'Pagamento de upgrade')
                    except Exception as _:
                        pass
                    
                    logger.info(f"Upgrade concluído: assinatura {assinatura.id} cancelada, nova assinatura {nova_assinatura.id} ativada")
                else:
                    logger.error(f"Nova assinatura não encontrada para upgrade da assinatura {assinatura.id}")
                    
            except Assinatura.DoesNotExist as e:
                logger.error(f"Assinatura não encontrada para upgrade: {str(e)}")
        
        # Verifica se é pagamento de reserva (começa com RESERVATION_)
        elif external_reference and external_reference.startswith('RESERVATION_'):
            logger.info(f"Processando pagamento de reserva: {external_reference}")
            try:
                # Extrai empresa_id e plano_id do externalReference
                parts = external_reference.replace('RESERVATION_', '').split('_')
                logger.info(f"Parts extraídas: {parts}")
                
                if len(parts) >= 2:
                    empresa_id = parts[0]
                    plano_id = parts[1]
                    logger.info(f"Empresa ID: {empresa_id}, Plano ID: {plano_id}")
                    
                    # Busca a assinatura pendente
                    assinatura = Assinatura.objects.filter(
                        empresa_id=empresa_id,
                        plano_id=plano_id,
                        payment_status='PENDING',
                        ativa=False
                    ).order_by('-criado_em').first()
                    
                    logger.info(f"Assinatura encontrada: {assinatura}")
                    
                    if assinatura:
                        # Cria a assinatura no Asaas agora que o pagamento foi confirmado
                        from empresas.models import Empresa
                        from assinaturas.models import Plano
                        
                        empresa = Empresa.objects.get(id=empresa_id)
                        plano = Plano.objects.get(id=plano_id)
                        
                        logger.info(f"Criando assinatura no Asaas para empresa {empresa.nome_fantasia} e plano {plano.nome}")
                        
                        # Cria a assinatura no Asaas com a mesma data de vencimento salva na reserva
                        override_date = None
                        try:
                            override_date = assinatura.fim.date().strftime('%Y-%m-%d') if assinatura.fim else None
                        except Exception:
                            override_date = None
                        subscription_response = self.create_subscription(
                            empresa,
                            plano,
                            extra_days=0,
                            due_date_override=override_date
                        )
                        logger.info(f"Assinatura criada no Asaas: {subscription_response}")
                        
                        # Atualiza a assinatura com o ID do Asaas
                        assinatura.asaas_subscription_id = subscription_response.get('id')
                        assinatura.payment_status = 'CONFIRMED'
                        assinatura.save(update_fields=['asaas_subscription_id', 'payment_status'])
                        
                        # Garante que apenas uma assinatura fique ativa; não cancela no Asaas aqui
                        self.ensure_single_active_subscription(empresa, assinatura)
                        # Desbloqueia empresa e cria histórico/notificação
                        try:
                            if not empresa.ativo:
                                empresa.ativo = True
                                empresa.save(update_fields=['ativo'])
                            from assinaturas.models import HistoricoPagamento
                            HistoricoPagamento.objects.create(
                                assinatura=assinatura,
                                tipo='ATIVACAO',
                                descricao='Pagamento confirmado (reserva) via Asaas',
                                valor_novo=assinatura.plano.preco
                            )
                            from painel_admin.notificacoes_utils import criar_notificacao_empresa_ativada, criar_notificacao_pagamento_recebido
                            criar_notificacao_empresa_ativada(empresa, assinatura.plano.nome)
                            valor = payment_data.get('value') or float(assinatura.plano.preco)
                            criar_notificacao_pagamento_recebido(assinatura, valor, 'Pagamento de assinatura')
                        except Exception as _:
                            pass

                        logger.info(f"Reserva convertida em assinatura: {assinatura.id}")
                    else:
                        logger.error(f"Assinatura pendente não encontrada para reserva: {external_reference}")
                        logger.error(f"Assinaturas pendentes existentes: {list(Assinatura.objects.filter(payment_status='PENDING', ativa=False).values('id', 'empresa_id', 'plano_id'))}")
                        
            except Exception as e:
                logger.error(f"Erro ao processar pagamento de reserva: {str(e)}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
        
        else:
            # Processamento normal para assinaturas regulares
            subscription_id = external_reference or payment_data.get('subscription')

            if subscription_id:
                try:
                    # Busca a assinatura mais recente com esse ID
                    assinatura = Assinatura.objects.filter(
                        asaas_subscription_id=subscription_id
                    ).order_by('-criado_em').first()
                    
                    if assinatura:
                        # Ativa/renova a assinatura e garante que seja a única ativa
                        previously_expired = bool(assinatura.expirada)
                        first_activation = (not assinatura.ativa and not assinatura.expirada)
                        assinatura.payment_status = 'CONFIRMED'
                        try:
                            if previously_expired:
                                # Estava expirada: reinicia ciclo a partir de agora
                                assinatura.inicio = timezone.now()
                                assinatura.fim = assinatura.inicio + relativedelta(days=assinatura.plano.duracao_dias)
                            elif assinatura.ativa:
                                # Já estava ativa: estende ciclo
                                if assinatura.fim:
                                    assinatura.fim = assinatura.fim + relativedelta(days=assinatura.plano.duracao_dias)
                            else:
                                # Primeira ativação (PENDING -> CONFIRMED): mantém fim calculado na criação
                                pass
                            if assinatura.fim:
                                assinatura.next_payment_date = assinatura.fim.date()
                        except Exception:
                            pass
                        assinatura.ativa = True
                        assinatura.expirada = False
                        assinatura.save(update_fields=['payment_status', 'inicio', 'fim', 'next_payment_date', 'ativa', 'expirada'])
                        
                        # Garante que apenas uma assinatura fique ativa
                        self.ensure_single_active_subscription(assinatura.empresa, assinatura)
                        # Desbloqueia empresa e cria histórico/notificação
                        try:
                            empresa = assinatura.empresa
                            if not empresa.ativo:
                                empresa.ativo = True
                                empresa.save(update_fields=['ativo'])
                            from assinaturas.models import HistoricoPagamento
                            HistoricoPagamento.objects.create(
                                assinatura=assinatura,
                                tipo='REATIVACAO' if previously_expired else ('ATIVACAO' if first_activation else 'EXTENSAO'),
                                descricao='Pagamento confirmado via Asaas',
                                valor_novo=assinatura.plano.preco,
                                data_inicio_nova= assinatura.inicio,
                                data_fim_nova= assinatura.fim
                            )
                            from painel_admin.notificacoes_utils import criar_notificacao_empresa_ativada, criar_notificacao_pagamento_recebido
                            criar_notificacao_empresa_ativada(empresa, assinatura.plano.nome)
                            valor = payment_data.get('value') or float(assinatura.plano.preco)
                            criar_notificacao_pagamento_recebido(assinatura, valor, 'Pagamento de assinatura (renovação)')
                        except Exception as _:
                            pass
                        
                        logger.info(f"Pagamento recebido para assinatura: {assinatura}")
                    else:
                        logger.warning(f"Assinatura não encontrada para subscription_id: {subscription_id}")
                    
                except Exception as e:
                    logger.error(f"Erro ao processar payment_received: {str(e)}")
            else:
                logger.warning("PAYMENT_RECEIVED sem externalReference")
    
    def _handle_payment_overdue(self, payload: Dict[str, Any]):
        """Processa evento de pagamento em atraso"""
        payment_data = payload.get('payment', {})
        subscription_id = payment_data.get('subscription')
        
        if subscription_id:
            try:
                # Busca a assinatura mais recente com esse ID
                assinatura = Assinatura.objects.filter(
                    asaas_subscription_id=subscription_id
                ).order_by('-criado_em').first()
                
                if assinatura:
                    assinatura.payment_status = 'OVERDUE'
                    assinatura.save(update_fields=['payment_status'])
                    # Opcional: bloquear empresa em atraso
                    try:
                        empresa = assinatura.empresa
                        if empresa.ativo:
                            empresa.ativo = False
                            empresa.save(update_fields=['ativo'])
                        from assinaturas.models import HistoricoPagamento
                        HistoricoPagamento.objects.create(
                            assinatura=assinatura,
                            tipo='BLOQUEIO',
                            descricao='Pagamento em atraso (OVERDUE) – bloqueio automático'
                        )
                        from painel_admin.notificacoes_utils import criar_notificacao_empresa_bloqueada
                        criar_notificacao_empresa_bloqueada(empresa, 'Pagamento em atraso no Asaas')
                    except Exception as _:
                        pass
                    
                    logger.info(f"Pagamento em atraso para assinatura: {assinatura}")
                else:
                    logger.warning(f"Assinatura não encontrada para subscription_id: {subscription_id}")
                
            except Exception as e:
                logger.error(f"Erro ao processar payment_overdue: {str(e)}")
