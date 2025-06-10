from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import RegexValidator, EmailValidator
import re

User = get_user_model()

class Empresa(models.Model):
    TIPO_CHOICES = [
        ('PJ', 'Pessoa Jurídica'),
        ('PF', 'Pessoa Física'),
    ]

    tipo = models.CharField(max_length=2, choices=TIPO_CHOICES)
    nome_fantasia = models.CharField(max_length=100)
    sigla = models.CharField(max_length=10)
    cnpj = models.CharField(max_length=18, null=True, blank=True)
    cpf = models.CharField(max_length=14, null=True, blank=True)
    razao_social = models.CharField(max_length=100, null=True, blank=True)
    inscricao_estadual = models.CharField(max_length=20, null=True, blank=True)
    inscricao_municipal = models.CharField(max_length=20, null=True, blank=True)
    registro_crmv_uf = models.CharField(max_length=2, null=True, blank=True)
    registro_crmv_numero = models.CharField(max_length=20, null=True, blank=True)
    email_comercial = models.EmailField()
    telefone1 = models.CharField(max_length=15)
    telefone2 = models.CharField(max_length=15, null=True, blank=True)
    telefone3 = models.CharField(max_length=15, null=True, blank=True)
    site = models.URLField(null=True, blank=True)
    redes_sociais = models.JSONField(default=list)
    horario_funcionamento = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.nome_fantasia

    def clean(self):
        if self.tipo == 'PJ':
            if not self.cnpj:
                raise ValidationError({'cnpj': 'CNPJ é obrigatório para Pessoa Jurídica'})
            if not self.razao_social:
                raise ValidationError({'razao_social': 'Razão Social é obrigatória para Pessoa Jurídica'})
        elif self.tipo == 'PF':
            if not self.cpf:
                raise ValidationError({'cpf': 'CPF é obrigatório para Pessoa Física'})

class Endereco(models.Model):
    empresa = models.OneToOneField(Empresa, on_delete=models.CASCADE, related_name='endereco')
    cep = models.CharField(max_length=9)
    endereco = models.CharField(max_length=200)
    numero = models.CharField(max_length=10)
    complemento = models.CharField(max_length=100, null=True, blank=True)
    ponto_referencia = models.CharField(max_length=200, null=True, blank=True)
    geolocalizacao = models.CharField(max_length=100, null=True, blank=True)
    bairro = models.CharField(max_length=100)
    cidade = models.CharField(max_length=100)
    estado = models.CharField(max_length=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.endereco}, {self.numero} - {self.bairro}"

    def clean(self):
        if self.cep and not re.match(r'^\d{8}$', self.cep):
            raise ValidationError({'cep': 'CEP deve conter 8 dígitos numéricos'})

class Logomarca(models.Model):
    empresa = models.OneToOneField(Empresa, on_delete=models.CASCADE, related_name='logomarca')
    imagem = models.ImageField(upload_to='logomarcas/')
    data_upload = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Logomarca de {self.empresa.nome_fantasia}"

class Parametros(models.Model):
    INFO_IDADE_CHOICES = [
        ('aniversario', 'Somente aniversário'),
        ('nascimento', 'Data de nascimento'),
    ]
    
    BLOQUEIO_CHOICES = [
        ('nao_bloquear', 'Não bloquear'),
        ('1_hora', '1 hora após a inclusão'),
        ('2_horas', '2 horas após a inclusão'),
        ('6_horas', '6 horas após a inclusão'),
        ('8_horas', '8 horas após a inclusão'),
        ('12_horas', '12 horas após a inclusão'),
        ('1_dia', '1 dia após a inclusão'),
        ('2_dias', '2 dias após a inclusão'),
        ('3_dias', '3 dias após a inclusão'),
        ('7_dias', '7 dias após a inclusão'),
        ('14_dias', '14 dias após a inclusão'),
        ('21_dias', '21 dias após a inclusão'),
        ('30_dias', '30 dias após a inclusão'),
    ]

    empresa = models.OneToOneField(Empresa, on_delete=models.CASCADE, related_name='parametros')
    fuso_horario = models.CharField(max_length=50)
    info_idade_cliente = models.CharField(max_length=20, choices=INFO_IDADE_CHOICES)
    arquivar_ficha_automatico = models.BooleanField(default=False)
    bloqueio_eventos_clinicos = models.CharField(max_length=20, choices=BLOQUEIO_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Parâmetros de {self.empresa.nome_fantasia}"

class Responsavel(models.Model):
    TIPO_CHOICES = [
        ('admin', 'Administrador'),
        ('financeiro', 'Financeiro'),
    ]

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='responsaveis')
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    emails_financeiro = models.JSONField(default=list)
    celular_financeiro = models.CharField(max_length=15, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.usuario.get_full_name()} - {self.get_tipo_display()}"

    class Meta:
        unique_together = ['empresa', 'tipo']
