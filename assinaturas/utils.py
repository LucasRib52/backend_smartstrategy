from decimal import Decimal, ROUND_HALF_UP


def calcular_prorata(valor_plano_atual, valor_novo_plano, dias_restantes: int, duracao_ciclo: int) -> Decimal:
    """
    Calcula o valor proporcional (prorrata) a ser cobrado na troca de plano.

    valor_plano_atual: Decimal ou float do valor do plano atual
    valor_novo_plano: Decimal ou float do valor do novo plano
    dias_restantes: dias que faltam para o fim do ciclo atual
    duracao_ciclo: duração total do ciclo (ex: 30 dias)

    Retorna Decimal com 2 casas.
    """
    valor_plano_atual = Decimal(valor_plano_atual)
    valor_novo_plano = Decimal(valor_novo_plano)

    # Se o novo plano é mais barato ou igual, não há cobrança imediata (downgrade/sem alteração)
    if valor_novo_plano <= valor_plano_atual:
        return Decimal("0.00")

    diferenca_total = valor_novo_plano - valor_plano_atual
    prorata = (diferenca_total * Decimal(dias_restantes)) / Decimal(max(duracao_ciclo, 1))

    # Arredonda para 2 casas decimais
    return prorata.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

