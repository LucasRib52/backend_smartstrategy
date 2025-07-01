from django.db import models
from datetime import date
from .utils import obter_clima  # Importa a função que obtém o clima atual
from empresas.models import Empresa
import logging

PLATAFORMA_CHOICES = [
    ('google', 'Google'),
    ('instagram', 'Instagram'),
    ('facebook', 'Facebook'),
]

class Venda(models.Model):
    # Campo de empresa
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='vendas', null=True, blank=True)

    # -------------------------------
    # Campos de Data e Informações Temporais
    # -------------------------------
    data = models.DateField("Data")  # Data da venda - ÚNICO CAMPO OBRIGATÓRIO
    mes = models.CharField("Mês", max_length=20, blank=True, null=True)  # Mês extraído da data
    ano = models.IntegerField("Ano", blank=True, null=True)  # Ano extraído da data
    semana = models.CharField("Semana", max_length=10, blank=True, null=True)  # Semana do ano referente à data

    # -------------------------------
    # Campos Relacionados ao Investimento
    # -------------------------------
    invest_realizado = models.DecimalField("Invest. Realizado (R$)", max_digits=10, decimal_places=2, null=True, blank=True)
    invest_projetado = models.DecimalField("Invest. Projetado (R$)", max_digits=10, decimal_places=2, null=True, blank=True)
    # Saldo do investimento: diferença entre o investido projetado e o realizado
    saldo_invest = models.DecimalField("Saldo Invest.", max_digits=10, decimal_places=2, blank=True, null=True)

    # -------------------------------
    # Campos de Vendas
    # -------------------------------
    vendas_google = models.DecimalField("Vendas Google (R$)", max_digits=10, decimal_places=2, default=0, null=True, blank=True)
    vendas_instagram = models.DecimalField("Vendas Instagram (R$)", max_digits=10, decimal_places=2, default=0, null=True, blank=True)
    vendas_facebook = models.DecimalField("Vendas Facebook (R$)", max_digits=10, decimal_places=2, default=0, null=True, blank=True)
    
    # -------------------------------
    # Campos de Faturamento
    # -------------------------------
    fat_proj = models.DecimalField("Faturamento Projetado (R$)", max_digits=10, decimal_places=2, null=True, blank=True)
    fat_camp_realizado = models.DecimalField("Faturamento Campanha Realizado (R$)", max_digits=10, decimal_places=2, null=True, blank=True)
    fat_geral = models.DecimalField("Faturamento Geral (R$)", max_digits=10, decimal_places=2, null=True, blank=True)
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
    ticket_medio_realizado = models.DecimalField("Ticket Médio Realizado (R$)", max_digits=10, decimal_places=2, null=True, blank=True)
    # ARPU (Receita Média por Usuário): faturamento dividido pelos clientes recorrentes
    arpu_realizado = models.DecimalField("ARPU Realizado (R$)", max_digits=10, decimal_places=2, blank=True, null=True)

    # -------------------------------
    # Métricas de Marketing
    # -------------------------------
    # Número de leads gerados na campanha
    leads = models.IntegerField("Leads", null=True, blank=True)
    # Número de novos clientes adquiridos
    clientes_novos = models.IntegerField("Clientes Novos", null=True, blank=True)
    # Número de clientes que efetuam compras recorrentes
    clientes_recorrentes = models.IntegerField("Clientes Recorrentes", null=True, blank=True)
    # Número de conversões realizadas (vendas ou ações desejadas)
    conversoes = models.IntegerField("Conversões", null=True, blank=True)
    # Taxa de Conversão: calculada como a razão entre clientes novos e leads
    # Observe que esse valor pode ficar muito baixo (e arredondar para 0.000) se a razão for pequena
    taxa_conversao = models.DecimalField("Taxa de Conversão", max_digits=5, decimal_places=3, blank=True, null=True)

    # -------------------------------
    # Outras Informações
    # -------------------------------
    # Clima: campo adicional para armazenar o clima obtido automaticamente
    clima = models.CharField("Clima", max_length=50, blank=True, null=True)

    plataforma = models.CharField(
        max_length=20,
        choices=PLATAFORMA_CHOICES,
        default='google',
        verbose_name='Plataforma'
    )

    def save(self, *args, **kwargs):
        # Atualiza os campos temporais (mês, ano, semana) com base na data informada
        if self.data:
            self.mes = self.data.strftime('%B')      # Exemplo: "January", "Fevereiro", etc.
            self.ano = self.data.year                 # Ano extraído da data
            self.semana = str(self.data.isocalendar().week)  # Número da semana no ano
        
        # Garante que campos decimal sejam None se não tiverem valor válido
        from decimal import Decimal, InvalidOperation
        
        # Garante que todos os campos tenham valores válidos
        self._ensure_valid_values()
        
        # Calcula o saldo de investimento (projetado - realizado)
        self.saldo_invest = self.invest_projetado - self.invest_realizado
        
        # Calcula o saldo do faturamento (geral - projetado)
        self.saldo_fat = self.fat_geral - self.fat_proj
        
        # Calcula o ROI e ROAS com base no faturamento da campanha e investimento realizado
        if self.invest_realizado != 0:
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
        if self.clientes_recorrentes != 0:
            self.arpu_realizado = self.fat_geral / self.clientes_recorrentes
        else:
            self.arpu_realizado = Decimal('0.00')
        
        # Calcula a taxa de conversão como a razão entre clientes novos e leads
        if self.leads != 0:
            self.taxa_conversao = self.clientes_novos / self.leads
            # Caso deseje armazenar a taxa em percentual, use:
            # self.taxa_conversao = (self.clientes_novos / self.leads) * 100
        else:
            self.taxa_conversao = Decimal('0.000')
        
        # Calcula o CAC (Custo de Aquisição de Cliente) dividindo o investimento realizado pelos clientes novos
        if self.clientes_novos != 0:
            self.cac_realizado = self.invest_realizado / self.clientes_novos
        else:
            self.cac_realizado = Decimal('0.00')
        
        # Se o campo clima estiver vazio, obtém a informação atual usando a função obter_clima()
        if not self.clima:
            self.clima = obter_clima()
        
        # Chama o método save() da classe base para efetivamente salvar o registro no banco de dados
        super().save(*args, **kwargs)
    
    def _ensure_valid_values(self):
        """Garante que todos os campos tenham valores válidos"""
        from decimal import Decimal, InvalidOperation
        
        # Função auxiliar para converter valores para Decimal de forma segura
        def safe_decimal(value, default=Decimal('0.00')):
            if value is None or value == '' or value == 'null' or value == 'undefined':
                return default
            try:
                if isinstance(value, str):
                    value = value.strip()
                    if value == '' or value == 'null' or value == 'undefined':
                        return default
                    value = value.replace(',', '.')
                return Decimal(str(value))
            except (InvalidOperation, ValueError, TypeError):
                return default
        
        # Função auxiliar para converter valores inteiros de forma segura
        def safe_integer(value, default=0):
            if value is None or value == '' or value == 'null' or value == 'undefined':
                return default
            try:
                if isinstance(value, str):
                    value = value.strip()
                    if value == '' or value == 'null' or value == 'undefined':
                        return default
                return int(value)
            except (ValueError, TypeError):
                return default
        
        # Converte campos decimal de forma segura com valor padrão 0.00
        self.invest_realizado = safe_decimal(self.invest_realizado)
        self.invest_projetado = safe_decimal(self.invest_projetado)
        self.vendas_google = safe_decimal(self.vendas_google)
        self.vendas_instagram = safe_decimal(self.vendas_instagram)
        self.vendas_facebook = safe_decimal(self.vendas_facebook)
        self.fat_proj = safe_decimal(self.fat_proj)
        self.fat_camp_realizado = safe_decimal(self.fat_camp_realizado)
        self.fat_geral = safe_decimal(self.fat_geral)
        
        # Converte campos inteiros de forma segura com valor padrão 0
        self.leads = safe_integer(self.leads)
        self.clientes_novos = safe_integer(self.clientes_novos)
        self.clientes_recorrentes = safe_integer(self.clientes_recorrentes)
        self.conversoes = safe_integer(self.conversoes)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Inicializa campos com valores padrão se não existirem
        if not self.pk:  # Se é um novo objeto
            self._initialize_defaults()
    
    def _initialize_defaults(self):
        """Inicializa campos com valores padrão"""
        from decimal import Decimal
        
        # Campos decimal com valor padrão 0.00
        decimal_fields = [
            'invest_realizado', 'invest_projetado', 'vendas_google', 
            'vendas_instagram', 'vendas_facebook', 'fat_proj', 
            'fat_camp_realizado', 'fat_geral', 'saldo_invest', 
            'saldo_fat', 'roi_realizado', 'roas_realizado', 
            'cac_realizado', 'ticket_medio_realizado', 'arpu_realizado', 
            'taxa_conversao'
        ]
        
        for field in decimal_fields:
            current_value = getattr(self, field)
            if current_value is None or current_value == '' or current_value == 'null':
                setattr(self, field, Decimal('0.00'))
        
        # Campos inteiros com valor padrão 0
        integer_fields = ['leads', 'clientes_novos', 'clientes_recorrentes', 'conversoes']
        for field in integer_fields:
            current_value = getattr(self, field)
            if current_value is None or current_value == '' or current_value == 'null':
                setattr(self, field, 0)

    def __str__(self):
        # Define a representação textual do objeto Venda
        return f"{self.data.strftime('%d/%m/%Y')} - Faturamento: R$ {self.fat_geral}"
