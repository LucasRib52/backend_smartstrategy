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

        self.stdout.write(self.style.SUCCESS(f"{quantidade} assinatura(s) marcadas como expiradas.")) 