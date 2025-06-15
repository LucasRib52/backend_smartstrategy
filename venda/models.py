from django.db import models
from datetime import date
from .utils import obter_clima  # Importa a função que obtém o clima atual
from empresas.models import Empresa
import logging

class Venda(models.Model):
    # Campo de empresa
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='vendas', null=True, blank=True)

    # -------------------------------
    # Campos de Data e Informações Temporais
    # -------------------------------
    data = models.DateField("Data")  # Data da venda
    mes = models.CharField("Mês", max_length=20, blank=True)  # Mês extraído da data
    ano = models.IntegerField("Ano", blank=True, null=True)  # Ano extraído da data
    semana = models.CharField("Semana", max_length=10, blank=True)  # Semana do ano referente à data

    # -------------------------------
    # Campos Relacionados ao Investimento
    # -------------------------------
    invest_realizado = models.DecimalField("Invest. Realizado (R$)", max_digits=10, decimal_places=2)
    invest_projetado = models.DecimalField("Invest. Projetado (R$)", max_digits=10, decimal_places=2)
    # Saldo do investimento: diferença entre o investido projetado e o realizado
    saldo_invest = models.DecimalField("Saldo Invest.", max_digits=10, decimal_places=2, blank=True, null=True)

    # -------------------------------
    # Campos de Vendas
    # -------------------------------
    vendas_google = models.DecimalField("Vendas Google (R$)", max_digits=10, decimal_places=2, default=0)
    vendas_instagram = models.DecimalField("Vendas Instagram (R$)", max_digits=10, decimal_places=2, default=0)
    vendas_facebook = models.DecimalField("Vendas Facebook (R$)", max_digits=10, decimal_places=2, default=0)
    
    # -------------------------------
    # Campos de Faturamento
    # -------------------------------
    fat_proj = models.DecimalField("Faturamento Projetado (R$)", max_digits=10, decimal_places=2)
    fat_camp_realizado = models.DecimalField("Faturamento Campanha Realizado (R$)", max_digits=10, decimal_places=2)
    fat_geral = models.DecimalField("Faturamento Geral (R$)", max_digits=10, decimal_places=2)
    # Saldo de faturamento: diferença entre o faturamento geral e o projetado
    saldo_fat = models.DecimalField("Saldo FAT", max_digits=10, decimal_places=2, blank=True, null=True)

    # -------------------------------
    # Indicadores de Desempenho (KPIs)
    # -------------------------------
    # ROI (Retorno sobre o Investimento): calculado a partir do faturamento de campanha e o investimento realizado
    roi_realizado = models.DecimalField("ROI Realizado", max_digits=6, decimal_places=2, blank=True, null=True)
    # ROAS (Retorno sobre o Gasto Publicitário): divisão entre o faturamento da campanha e o investimento realizado
    roas_realizado = models.DecimalField("ROAS Realizado", max_digits=6, decimal_places=2, blank=True, null=True)
    # CAC (Custo de Aquisição de Cliente): investimento realizado dividido pelo número de clientes novos
    cac_realizado = models.DecimalField("CAC Realizado (R$)", max_digits=10, decimal_places=2, blank=True, null=True)

    # -------------------------------
    # Métricas de Receita
    # -------------------------------
    # Ticket médio: valor médio por transação realizada
    ticket_medio_realizado = models.DecimalField("Ticket Médio Realizado (R$)", max_digits=10, decimal_places=2)
    # ARPU (Receita Média por Usuário): faturamento dividido pelos clientes recorrentes
    arpu_realizado = models.DecimalField("ARPU Realizado (R$)", max_digits=10, decimal_places=2, blank=True, null=True)

    # -------------------------------
    # Métricas de Marketing
    # -------------------------------
    # Número de leads gerados na campanha
    leads = models.IntegerField("Leads")
    # Número de novos clientes adquiridos
    clientes_novos = models.IntegerField("Clientes Novos")
    # Número de clientes que efetuam compras recorrentes
    clientes_recorrentes = models.IntegerField("Clientes Recorrentes")
    # Número de conversões realizadas (vendas ou ações desejadas)
    conversoes = models.IntegerField("Conversões")
    # Taxa de Conversão: calculada como a razão entre clientes novos e leads
    # Observe que esse valor pode ficar muito baixo (e arredondar para 0.000) se a razão for pequena
    taxa_conversao = models.DecimalField("Taxa de Conversão", max_digits=5, decimal_places=3, blank=True, null=True)

    # -------------------------------
    # Outras Informações
    # -------------------------------
    # Clima: campo adicional para armazenar o clima obtido automaticamente
    clima = models.CharField("Clima", max_length=50, blank=True, null=True)

    def save(self, *args, **kwargs):
        # Atualiza os campos temporais (mês, ano, semana) com base na data informada
        if self.data:
            self.mes = self.data.strftime('%B')      # Exemplo: "January", "Fevereiro", etc.
            self.ano = self.data.year                 # Ano extraído da data
            self.semana = str(self.data.isocalendar().week)  # Número da semana no ano
        
        # Calcula o saldo de investimento (projetado - realizado)
        if self.invest_projetado and self.invest_realizado:
            self.saldo_invest = self.invest_projetado - self.invest_realizado
        
        # Calcula o saldo do faturamento (geral - projetado)
        if self.fat_geral and self.fat_proj:
            self.saldo_fat = self.fat_geral - self.fat_proj
        
        # Calcula o ROI e ROAS com base no faturamento da campanha e investimento realizado
        if self.invest_realizado and self.invest_realizado != 0:
            logger = logging.getLogger(__name__)
            logger.warning(f"[ROI CALCULATION] Valores para cálculo:")
            logger.warning(f"Investimento realizado: {self.invest_realizado}")
            logger.warning(f"Faturamento campanha: {self.fat_camp_realizado}")
            logger.warning(f"Faturamento geral: {self.fat_geral}")
            
            # Se o faturamento da campanha for igual ao investimento, usa o faturamento geral
            if self.fat_camp_realizado == self.invest_realizado:
                logger.warning("[ROI CALCULATION] Usando faturamento geral para ROI")
                self.roi_realizado = (self.fat_geral - self.invest_realizado) / self.invest_realizado
            else:
                logger.warning("[ROI CALCULATION] Usando faturamento campanha para ROI")
                self.roi_realizado = (self.fat_camp_realizado - self.invest_realizado) / self.invest_realizado
            
            logger.warning(f"[ROI CALCULATION] ROI calculado: {self.roi_realizado}")
            self.roas_realizado = self.fat_camp_realizado / self.invest_realizado
        
        # Calcula o ARPU (Receita Média por Usuário) com base nos clientes recorrentes
        if self.clientes_recorrentes and self.clientes_recorrentes != 0:
            self.arpu_realizado = self.fat_geral / self.clientes_recorrentes
        
        # Calcula a taxa de conversão como a razão entre clientes novos e leads
        if self.leads and self.leads != 0:
            self.taxa_conversao = self.clientes_novos / self.leads
            # Caso deseje armazenar a taxa em percentual, use:
            # self.taxa_conversao = (self.clientes_novos / self.leads) * 100
        
        # Calcula o CAC (Custo de Aquisição de Cliente) dividindo o investimento realizado pelos clientes novos
        if self.clientes_novos and self.clientes_novos != 0:
            self.cac_realizado = self.invest_realizado / self.clientes_novos
        
        # Se o campo clima estiver vazio, obtém a informação atual usando a função obter_clima()
        if not self.clima:
            self.clima = obter_clima()
        
        # Chama o método save() da classe base para efetivamente salvar o registro no banco de dados
        super().save(*args, **kwargs)

    def __str__(self):
        # Define a representação textual do objeto Venda
        return f"{self.data.strftime('%d/%m/%Y')} - Faturamento: R$ {self.fat_geral}"
