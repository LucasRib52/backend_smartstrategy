from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Empresa, Endereco, Logomarca, Responsavel
from assinaturas.serializers import AssinaturaSerializer
from django.utils import timezone
import re

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email']

class EnderecoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Endereco
        fields = '__all__'

    def validate_cep(self, value):
        if not re.match(r'^\d{8}$', value):
            raise serializers.ValidationError('CEP deve conter 8 dígitos numéricos')
        return value

class LogomarcaSerializer(serializers.ModelSerializer):
    imagem = serializers.SerializerMethodField()

    class Meta:
        model = Logomarca
        fields = '__all__'
        read_only_fields = ['data_upload']

    def get_imagem(self, obj):
        request = self.context.get('request')
        if obj.imagem and hasattr(obj.imagem, 'url'):
            url = obj.imagem.url
            if request is not None:
                return request.build_absolute_uri(url)
            return url
        return None

    def validate_imagem(self, value):
        if value:
            # Validar o tamanho do arquivo (máximo 5MB)
            if value.size > 5 * 1024 * 1024:
                raise serializers.ValidationError("O arquivo deve ter no máximo 5MB")
            
            # Validar o tipo do arquivo
            if not value.content_type.startswith('image/'):
                raise serializers.ValidationError("O arquivo deve ser uma imagem")
            
            # Validar a extensão
            if not value.name.lower().endswith(('.png', '.jpg', '.jpeg')):
                raise serializers.ValidationError("O arquivo deve ser PNG, JPG ou JPEG")
        
        return value

class ResponsavelSerializer(serializers.ModelSerializer):
    usuario = UserSerializer(read_only=True)
    usuario_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source='usuario',
        write_only=True
    )

    class Meta:
        model = Responsavel
        fields = ['id', 'empresa', 'usuario', 'usuario_id', 'tipo', 'emails_financeiro', 'celular_financeiro', 'created_at', 'updated_at']
        read_only_fields = ['empresa']

    def validate(self, data):
        # Se estiver atualizando, não precisa validar o tipo
        if self.instance:
            return data

        # Se estiver criando, verifica se já existe um responsável do mesmo tipo
        empresa = self.context.get('empresa')
        tipo = data.get('tipo')
        
        if empresa and tipo:
            if Responsavel.objects.filter(empresa=empresa, tipo=tipo).exists():
                raise serializers.ValidationError(f'Já existe um responsável do tipo {tipo} para esta empresa')
        
        return data

class EmpresaSerializer(serializers.ModelSerializer):
    endereco = EnderecoSerializer(read_only=True)
    logomarca = LogomarcaSerializer(read_only=True)
    responsaveis = ResponsavelSerializer(many=True, read_only=True)
    assinatura_ativa = serializers.SerializerMethodField()
    ativo = serializers.BooleanField(read_only=True)
    plano_expirado = serializers.SerializerMethodField()

    class Meta:
        model = Empresa
        fields = [
            'id', 'tipo', 'nome_fantasia', 'sigla', 'cnpj', 'cpf', 'razao_social',
            'inscricao_estadual', 'inscricao_municipal',
            'email_comercial', 'telefone1', 'telefone2',
            'site', 'redes_sociais', 'horario_funcionamento',
            'endereco', 'logomarca', 'responsaveis',
            'ativo', 'assinatura_ativa', 'plano_expirado',
            'created_at', 'updated_at'
        ]
        extra_kwargs = {
            'nome_fantasia': {
                'required': False,
                'allow_blank': True,
                'allow_null': True,
            }
        }

    def _is_valid_cnpj_digits(self, cnpj_num: str) -> bool:
        """Valida dígitos verificadores do CNPJ (apenas números)."""
        if len(cnpj_num) != 14 or len(set(cnpj_num)) == 1:
            return False

        def calc_dv(base, pesos):
            soma = sum(int(d) * p for d, p in zip(base, pesos))
            resto = soma % 11
            return '0' if resto < 2 else str(11 - resto)

        dv1 = calc_dv(cnpj_num[:12], [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
        dv2 = calc_dv(cnpj_num[:13], [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
        return cnpj_num[-2:] == dv1 + dv2

    def validate_cnpj(self, value):
        # Em atualização da empresa (self.instance existe), não travamos pelo CNPJ.
        if self.instance:
            return value

        digits = re.sub(r'[^0-9]', '', value)

        if not digits.isdigit() or len(digits) != 14 or not self._is_valid_cnpj_digits(digits):
            raise serializers.ValidationError('CNPJ inválido (dígitos verificadores incorretos)')
        
        return value

    def validate_telefone1(self, value):
        if not value:
            return value
        cleaned_value = re.sub(r'\D', '', value)
        if not re.match(r'^\d{10,11}$', cleaned_value):
            raise serializers.ValidationError('Telefone deve conter 10 ou 11 dígitos numéricos')
        return cleaned_value

    def validate_email_comercial(self, value):
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', value):
            raise serializers.ValidationError('Email inválido')
        return value

    def get_assinatura_ativa(self, obj):
        try:
            assinatura = obj.assinatura_ativa
            # Reconciliação com Asaas SEMPRE: garante bloqueio/desbloqueio mesmo sem webhook
            try:
                if getattr(obj, 'asaas_customer_id', None):
                    from asaas.services import AsaasService
                    service = AsaasService()
                    remote = service.list_customer_subscriptions(obj.asaas_customer_id)
                    remote_data = remote.get('data', []) if isinstance(remote, dict) else []
                    active_remote_ids = {
                        item.get('id') for item in remote_data
                        if str(item.get('status', '')).upper() in {'ACTIVE'}
                    }
                    if not active_remote_ids and assinatura:
                        # Não existe assinatura ativa no Asaas → bloqueia e marca local como cancelada/expirada
                        assinatura.payment_status = 'CANCELLED'
                        assinatura.ativa = False
                        assinatura.expirada = True
                        assinatura.save(update_fields=['payment_status', 'ativa', 'expirada'])
                        if obj.ativo:
                            obj.ativo = False
                            obj.save(update_fields=['ativo'])
                        assinatura = None
                    elif active_remote_ids:
                        # Existe ativa no Asaas → garante desbloqueio e ativa correspondente local
                        if not obj.ativo:
                            obj.ativo = True
                            obj.save(update_fields=['ativo'])
                        if assinatura and assinatura.asaas_subscription_id in active_remote_ids:
                            if assinatura.payment_status != 'CONFIRMED' or assinatura.expirada or not assinatura.ativa:
                                assinatura.payment_status = 'CONFIRMED'
                                assinatura.ativa = True
                                assinatura.expirada = False
                                assinatura.save(update_fields=['payment_status', 'ativa', 'expirada'])
                        else:
                            from assinaturas.models import Assinatura as AssinaturaModel
                            candidato = AssinaturaModel.objects.filter(
                                empresa=obj,
                                asaas_subscription_id__in=list(active_remote_ids)
                            ).order_by('-criado_em').first()
                            if candidato:
                                AssinaturaModel.objects.filter(empresa=obj, ativa=True).exclude(id=candidato.id).update(
                                    ativa=False, expirada=True, payment_status='CANCELLED'
                                )
                                candidato.payment_status = 'CONFIRMED'
                                candidato.ativa = True
                                candidato.expirada = False
                                candidato.save(update_fields=['payment_status', 'ativa', 'expirada'])
                                assinatura = candidato
            except Exception:
                pass
            # Auto-expiração: se a assinatura ativa passou do fim e ainda não foi marcada, expira e bloqueia
            if assinatura and assinatura.fim <= timezone.now() and not assinatura.expirada:
                try:
                    assinatura.marcar_como_expirada()
                    # Cancela no Asaas também
                    try:
                        if assinatura.asaas_subscription_id:
                            from asaas.services import AsaasService
                            AsaasService().cancel_subscription(assinatura)
                    except Exception:
                        pass
                    empresa = assinatura.empresa
                    if empresa.ativo:
                        empresa.ativo = False
                        empresa.save(update_fields=['ativo'])
                    # Notificações e histórico
                    try:
                        from painel_admin.notificacoes_utils import criar_notificacao_plano_expirado, criar_notificacao_empresa_bloqueada
                        criar_notificacao_plano_expirado(assinatura, "Expiração automática por tempo")
                        criar_notificacao_empresa_bloqueada(empresa, "Bloqueio automático por expiração de plano")
                    except Exception:
                        pass
                    try:
                        from assinaturas.models import HistoricoPagamento
                        HistoricoPagamento.objects.create(
                            assinatura=assinatura,
                            tipo='EXPIRACAO',
                            descricao='Plano expirado automaticamente ao consultar status',
                            data_fim_anterior=assinatura.fim
                        )
                    except Exception:
                        pass
                except Exception:
                    pass
                # Recarrega assinatura ativa (pode não existir mais)
                assinatura = obj.assinatura_ativa
            if not assinatura:
                # Reconciliação com Asaas se não houver assinatura local ativa
                try:
                    if getattr(obj, 'asaas_customer_id', None):
                        from asaas.services import AsaasService
                        service = AsaasService()
                        remote = service.list_customer_subscriptions(obj.asaas_customer_id)
                        remote_data = remote.get('data', []) if isinstance(remote, dict) else []
                        active_remote_ids = {
                            item.get('id') for item in remote_data
                            if str(item.get('status', '')).upper() in {'ACTIVE'}
                        }
                        if active_remote_ids:
                            # Há ativa no Asaas; tenta alinhar local
                            from assinaturas.models import Assinatura as AssinaturaModel
                            candidato = AssinaturaModel.objects.filter(
                                empresa=obj,
                                asaas_subscription_id__in=list(active_remote_ids)
                            ).order_by('-criado_em').first()
                            if candidato:
                                AssinaturaModel.objects.filter(empresa=obj, ativa=True).exclude(id=candidato.id).update(
                                    ativa=False, expirada=True, payment_status='CANCELLED'
                                )
                                candidato.payment_status = 'CONFIRMED'
                                candidato.ativa = True
                                candidato.expirada = False
                                candidato.save(update_fields=['payment_status', 'ativa', 'expirada'])
                                assinatura = candidato
                                if not obj.ativo:
                                    obj.ativo = True
                                    obj.save(update_fields=['ativo'])
                except Exception:
                    pass
                if not assinatura:
                    return None
            # Auto-desbloqueio: se há assinatura ativa e empresa está bloqueada, desbloqueia
            try:
                if assinatura.ativa and not assinatura.expirada and not obj.ativo:
                    obj.ativo = True
                    obj.save(update_fields=['ativo'])
                    try:
                        from painel_admin.notificacoes_utils import criar_notificacao_empresa_ativada
                        criar_notificacao_empresa_ativada(obj, assinatura.plano.nome)
                    except Exception:
                        pass
                    try:
                        from assinaturas.models import HistoricoPagamento
                        HistoricoPagamento.objects.create(
                            assinatura=assinatura,
                            tipo='DESBLOQUEIO',
                            descricao='Desbloqueio automático por assinatura ativa confirmada'
                        )
                    except Exception:
                        pass
            except Exception:
                pass
            context = self.context.copy()
            context['now'] = timezone.now()
            return AssinaturaSerializer(assinatura, context=context).data
        except Exception as e:
            print(f"Erro ao serializar assinatura ativa: {str(e)}")
            return None

    def get_plano_expirado(self, obj):
        try:
            assinatura = obj.assinatura_ativa
            if assinatura:
                return assinatura.expirada
            # Sem assinatura ativa: considera expirado se última assinatura existir e estiver expirada
            ultima = obj.assinaturas.order_by('-inicio').first()
            if ultima:
                return True if ultima.expirada or ultima.fim <= timezone.now() else False
            return True
        except Exception as e:
            print(f"Erro ao verificar plano expirado: {str(e)}")
            return True