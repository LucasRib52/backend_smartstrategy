from django.core.management.base import BaseCommand
from assinaturas.models import Plano

# Tabela de planos padrão (id, codigo, nome, preco, duracao_dias)
PLANOS_PADRAO = [
    (1, 'FREE', 'Período de Teste', 0, 7),
    (2, 'BASIC', 'Assinatura Básica', 69.90, 30),
    (3, 'PRO', 'Plano Gold Pro', 99.90, 30),
    (4, 'ENTERPRISE', 'Plano Empresarial', 199.90, 30),
]


class Command(BaseCommand):
    help = 'Cria (ou atualiza) os planos padrão com ids 1-4.'

    def handle(self, *args, **options):
        created = 0
        updated = 0
        for pk, codigo, nome, preco, dias in PLANOS_PADRAO:
            obj, was_created = Plano.objects.update_or_create(
                pk=pk,
                defaults=dict(codigo=codigo, nome=nome, preco=preco, duracao_dias=dias, ativo=True),
            )
            if was_created:
                created += 1
            else:
                updated += 1
        self.stdout.write(self.style.SUCCESS(f'Planos criados/atualizados. Novos: {created}, Atualizados: {updated}')) 