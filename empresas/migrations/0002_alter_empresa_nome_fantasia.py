# Generated by Django 4.2.21 on 2025-06-12 20:40

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('empresas', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='empresa',
            name='nome_fantasia',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ]
