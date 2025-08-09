from django.core.management.base import BaseCommand
from django.utils import timezone

from assinaturas.models import Assinatura


class Command(BaseCommand):
    help = 'Verifica assinaturas vencidas e marca-as como expiradas/desativa acesso.'

    def handle(self, *args, **options):
        agora = timezone.now()
        expiradas = Assinatura.objects.filter(fim__lt=agora, expirada=False)
        quantidade = expiradas.count()

        for assinatura in expiradas:
            assinatura.marcar_como_expirada()
            try:
                empresa = assinatura.empresa
                if empresa.ativo:
                    empresa.ativo = False
                    empresa.save(update_fields=['ativo'])
                # Notificações e histórico
                try:
                    from painel_admin.notificacoes_utils import criar_notificacao_plano_expirado, criar_notificacao_empresa_bloqueada
                    criar_notificacao_plano_expirado(assinatura, "Expiração automática (cron)")
                    criar_notificacao_empresa_bloqueada(empresa, "Bloqueio automático por expiração de plano (cron)")
                except Exception:
                    pass
                try:
                    from assinaturas.models import HistoricoPagamento
                    HistoricoPagamento.objects.create(
                        assinatura=assinatura,
                        tipo='EXPIRACAO',
                        descricao='Plano expirado automaticamente via comando',
                        data_fim_anterior=assinatura.fim
                    )
                except Exception:
                    pass
            except Exception:
                pass

        self.stdout.write(self.style.SUCCESS(f"{quantidade} assinatura(s) marcadas como expiradas.")) 