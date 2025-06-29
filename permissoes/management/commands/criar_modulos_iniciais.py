from django.core.management.base import BaseCommand
from permissoes.models import ModuloPermissao

class Command(BaseCommand):
    help = 'Cria os módulos iniciais do sistema (Marketing e Financeiro)'

    def handle(self, *args, **options):
        modulos = [
            {
                'codigo': 'marketing',
                'nome': 'Marketing',
                'descricao': 'Módulo de gestão de marketing e campanhas',
                'ativo': True
            },
            {
                'codigo': 'financeiro',
                'nome': 'Financeiro',
                'descricao': 'Módulo de gestão financeira e contábil',
                'ativo': True
            }
        ]

        for modulo_data in modulos:
            modulo, created = ModuloPermissao.objects.get_or_create(
                codigo=modulo_data['codigo'],
                defaults=modulo_data
            )

            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'Módulo "{modulo.nome}" criado com sucesso!')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Módulo "{modulo.nome}" já existe.')
                ) 