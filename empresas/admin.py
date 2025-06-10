from django.contrib import admin
from .models import Empresa, Endereco, Logomarca, Parametros, Responsavel

@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ('nome_fantasia', 'tipo', 'cnpj', 'email_comercial', 'telefone1')
    search_fields = ('nome_fantasia', 'cnpj', 'email_comercial')
    list_filter = ('tipo',)

@admin.register(Endereco)
class EnderecoAdmin(admin.ModelAdmin):
    list_display = ('empresa', 'endereco', 'numero', 'bairro', 'cidade', 'estado')
    search_fields = ('endereco', 'bairro', 'cidade')
    list_filter = ('estado',)

@admin.register(Logomarca)
class LogomarcaAdmin(admin.ModelAdmin):
    list_display = ('empresa', 'data_upload')
    search_fields = ('empresa__nome_fantasia',)

@admin.register(Parametros)
class ParametrosAdmin(admin.ModelAdmin):
    list_display = ('empresa', 'fuso_horario', 'info_idade_cliente', 'arquivar_ficha_automatico')
    search_fields = ('empresa__nome_fantasia',)
    list_filter = ('fuso_horario', 'info_idade_cliente', 'arquivar_ficha_automatico')

@admin.register(Responsavel)
class ResponsavelAdmin(admin.ModelAdmin):
    list_display = ('empresa', 'usuario', 'tipo', 'celular_financeiro')
    search_fields = ('empresa__nome_fantasia', 'usuario__username', 'usuario__email')
    list_filter = ('tipo',)
