from django.core.management.base import BaseCommand
from assinaturas.models import Plano

# Tabela de planos padrão (id, codigo, nome, preco, duracao_dias)
PLANOS_PADRAO = [
    (1, 'TRIAL', 'Período de Teste (Grátis)', 0, 3),
]


class Command(BaseCommand):
    help = 'Cria o plano gratuito de teste com 3 dias.'

    def handle(self, *args, **options):
        created = 0
        updated = 0
        for pk, codigo, nome, preco, dias in PLANOS_PADRAO:
            obj, was_created = Plano.objects.update_or_create(
                pk=pk,
                defaults=dict(
                    codigo=codigo, 
                    nome=nome, 
                    preco=preco, 
                    duracao_dias=dias, 
                    ativo=True,
                    trial_days=3,
                    # Permissões - todas liberadas no trial
                    acesso_financeiro=True,
                    acesso_marketing=True,
                    acesso_influencer=True,
                    acesso_analytics=True,
                    # Vantagens e desvantagens padrão
                    vantagens=[
                        "Acesso completo a todos os módulos",
                        "Teste gratuito por 3 dias",
                        "Interface moderna e intuitiva",
                        "Suporte por email"
                    ],
                    desvantagens=[
                        "Apenas 3 dias de acesso",
                        "Sem recursos avançados",
                        "Limitações de uso"
                    ],
                    descricao="Plano gratuito para testar todas as funcionalidades do sistema por 3 dias."
                ),
            )
            if was_created:
                created += 1
            else:
                updated += 1
        self.stdout.write(self.style.SUCCESS(f'Plano gratuito criado/atualizado. Novos: {created}, Atualizados: {updated}')) 