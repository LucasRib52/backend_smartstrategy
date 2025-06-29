from datetime import timedelta

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from empresas.models import Empresa
from .models import Plano, Assinatura


@receiver(post_save, sender=Empresa)
def criar_trial_para_empresa(sender, instance: Empresa, created: bool, **kwargs):
    """Ao criar uma empresa, vincula uma assinatura trial de 7 dias se não existir."""
    if not created:
        return

    # Garante que exista um Plano TRIAL
    plano_trial, _ = Plano.objects.get_or_create(
        codigo='TRIAL',
        defaults={
            'nome': 'Período de Teste',
            'preco': 0,
            'duracao_dias': 7,
        },
    )

    agora = timezone.now()

    assinatura_trial = Assinatura.objects.create(
        empresa=instance,
        plano=plano_trial,
        inicio=agora,
        fim=agora + timedelta(days=plano_trial.duracao_dias),
    )
    
    # Criar notificações automáticas
    try:
        from painel_admin.notificacoes_utils import (
            criar_notificacao_empresa_criada,
            criar_notificacao_assinatura_criada
        )
        
        # Notificação de empresa criada
        criar_notificacao_empresa_criada(instance)
        
        # Notificação de assinatura trial criada
        criar_notificacao_assinatura_criada(assinatura_trial)
        
    except ImportError:
        pass  # Se o módulo de notificações não estiver disponível, apenas ignora 