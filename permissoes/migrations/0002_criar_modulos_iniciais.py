from django.db import migrations

def criar_modulos(apps, schema_editor):
    ModuloPermissao = apps.get_model('permissoes', 'ModuloPermissao')
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
        },
        # Adicione mais módulos aqui se quiser!
    ]
    for modulo in modulos:
        ModuloPermissao.objects.get_or_create(codigo=modulo['codigo'], defaults=modulo)

class Migration(migrations.Migration):

    dependencies = [
        ('permissoes', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(criar_modulos),
    ] 