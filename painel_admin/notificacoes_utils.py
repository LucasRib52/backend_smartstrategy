from .models import NotificacaoAdmin
from django.utils import timezone


def criar_notificacao_empresa_criada(empresa):
    """Cria notificação quando uma empresa é criada"""
    razao_social = empresa.razao_social or ''
    primeiro_nome = razao_social.split()[0] if razao_social else (empresa.nome_fantasia or str(empresa)).split()[0]
    cnpj = empresa.cnpj or ''
    nome_empresa = empresa.nome_fantasia or empresa.razao_social or str(empresa)
    NotificacaoAdmin.criar_notificacao(
        tipo='empresa_criada',
        titulo=f'Nova empresa criada: {primeiro_nome} (CNPJ: {cnpj})',
        mensagem=f'Empresa {empresa.tipo} "{nome_empresa}" (CNPJ: {cnpj}) foi criada com sucesso.',
        prioridade='media',
        empresa=empresa,
        dados_extras={
            'tipo_empresa': empresa.tipo,
            'email': empresa.email_comercial,
            'telefone': empresa.telefone1,
            'cnpj': cnpj
        }
    )


def criar_notificacao_empresa_bloqueada(empresa, motivo="Bloqueio manual"):
    """Cria notificação quando uma empresa é bloqueada"""
    NotificacaoAdmin.criar_notificacao(
        tipo='empresa_bloqueada',
        titulo=f'Empresa bloqueada: {empresa.nome_fantasia or empresa.razao_social}',
        mensagem=f'Empresa "{empresa.nome_fantasia or empresa.razao_social}" foi bloqueada. Motivo: {motivo}',
        prioridade='alta',
        empresa=empresa,
        dados_extras={
            'motivo': motivo,
            'email': empresa.email_comercial
        }
    )


def criar_notificacao_empresa_ativada(empresa, plano_nome=None):
    """Cria notificação quando uma empresa é ativada"""
    mensagem = f'Empresa "{empresa.nome_fantasia or empresa.razao_social}" foi ativada'
    if plano_nome:
        mensagem += f' com plano {plano_nome}'
    mensagem += '.'
    
    NotificacaoAdmin.criar_notificacao(
        tipo='empresa_ativada',
        titulo=f'Empresa ativada: {empresa.nome_fantasia or empresa.razao_social}',
        mensagem=mensagem,
        prioridade='media',
        empresa=empresa,
        dados_extras={
            'plano': plano_nome,
            'email': empresa.email_comercial
        }
    )


def criar_notificacao_assinatura_criada(assinatura):
    """Cria notificação quando uma assinatura é criada"""
    NotificacaoAdmin.criar_notificacao(
        tipo='assinatura_criada',
        titulo=f'Nova assinatura criada: {assinatura.empresa.nome_fantasia or assinatura.empresa.razao_social}',
        mensagem=f'Assinatura do plano {assinatura.plano.nome} criada para empresa "{assinatura.empresa.nome_fantasia or assinatura.empresa.razao_social}". Valor: R$ {assinatura.plano.preco}',
        prioridade='media',
        empresa=assinatura.empresa,
        dados_extras={
            'plano': assinatura.plano.nome,
            'valor': float(assinatura.plano.preco),
            'duracao_dias': assinatura.plano.duracao_dias,
            'data_inicio': assinatura.inicio.isoformat(),
            'data_fim': assinatura.fim.isoformat()
        }
    )


def criar_notificacao_plano_expirado(assinatura, motivo="Expiração automática"):
    """Cria notificação quando um plano expira"""
    NotificacaoAdmin.criar_notificacao(
        tipo='plano_expirado',
        titulo=f'Plano expirado: {assinatura.empresa.nome_fantasia or assinatura.empresa.razao_social}',
        mensagem=f'Plano {assinatura.plano.nome} da empresa "{assinatura.empresa.nome_fantasia or assinatura.empresa.razao_social}" expirou. Motivo: {motivo}',
        prioridade='alta',
        empresa=assinatura.empresa,
        dados_extras={
            'plano': assinatura.plano.nome,
            'motivo': motivo,
            'data_expiracao': assinatura.fim.isoformat(),
            'email': assinatura.empresa.email_comercial
        }
    )


def criar_notificacao_plano_renovado(assinatura, plano_anterior=None):
    """Cria notificação quando um plano é renovado"""
    mensagem = f'Plano da empresa "{assinatura.empresa.nome_fantasia or assinatura.empresa.razao_social}" foi renovado'
    if plano_anterior:
        mensagem += f' de {plano_anterior.nome} para {assinatura.plano.nome}'
    mensagem += '.'
    
    NotificacaoAdmin.criar_notificacao(
        tipo='plano_renovado',
        titulo=f'Plano renovado: {assinatura.empresa.nome_fantasia or assinatura.empresa.razao_social}',
        mensagem=mensagem,
        prioridade='media',
        empresa=assinatura.empresa,
        dados_extras={
            'plano_atual': assinatura.plano.nome,
            'plano_anterior': plano_anterior.nome if plano_anterior else None,
            'valor': float(assinatura.plano.preco),
            'data_inicio': assinatura.inicio.isoformat(),
            'data_fim': assinatura.fim.isoformat()
        }
    )


def criar_notificacao_pagamento_recebido(assinatura, valor, tipo_pagamento="Pagamento"):
    """Cria notificação quando um pagamento é recebido"""
    NotificacaoAdmin.criar_notificacao(
        tipo='pagamento_recebido',
        titulo=f'Pagamento recebido: {assinatura.empresa.nome_fantasia or assinatura.empresa.razao_social}',
        mensagem=f'{tipo_pagamento} de R$ {valor} recebido da empresa "{assinatura.empresa.nome_fantasia or assinatura.empresa.razao_social}" para o plano {assinatura.plano.nome}',
        prioridade='alta',
        empresa=assinatura.empresa,
        dados_extras={
            'valor': float(valor),
            'tipo_pagamento': tipo_pagamento,
            'plano': assinatura.plano.nome,
            'email': assinatura.empresa.email_comercial
        }
    )


def criar_notificacao_usuario_criado(usuario, empresa=None):
    """Cria notificação quando um usuário PF é criado"""
    # Buscar nome e CPF do perfil PF
    try:
        profile = usuario.person_profile
        nome_usuario = profile.name or usuario.get_full_name() or usuario.username or usuario.email
        cpf = profile.cpf or ''
    except Exception:
        nome_usuario = usuario.get_full_name() or usuario.username or usuario.email
        cpf = ''
    mensagem = f'Novo usuário PF criado: {nome_usuario} (CPF: {cpf})'
    if empresa:
        razao_social = empresa.razao_social or ''
        primeiro_nome = razao_social.split()[0] if razao_social else (empresa.nome_fantasia or str(empresa)).split()[0]
        cnpj = empresa.cnpj or ''
        mensagem += f' para empresa {primeiro_nome} (CNPJ: {cnpj})'
    mensagem += '.'
    
    NotificacaoAdmin.criar_notificacao(
        tipo='usuario_criado',
        titulo=f'Novo usuário PF: {nome_usuario} (CPF: {cpf})',
        mensagem=mensagem,
        prioridade='baixa',
        usuario=usuario,
        empresa=empresa,
        dados_extras={
            'email': usuario.email,
            'username': usuario.username,
            'cpf': cpf,
            'empresa': primeiro_nome if empresa else None,
            'cnpj_empresa': cnpj if empresa else None
        }
    )


def criar_notificacao_sistema(titulo, mensagem, prioridade='media', dados_extras=None):
    """Cria notificação do sistema"""
    NotificacaoAdmin.criar_notificacao(
        tipo='sistema',
        titulo=titulo,
        mensagem=mensagem,
        prioridade=prioridade,
        dados_extras=dados_extras or {}
    ) 