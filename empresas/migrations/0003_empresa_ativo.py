# Generated by Django 4.2.21 on 2025-06-24 19:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('empresas', '0002_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='empresa',
            name='ativo',
            field=models.BooleanField(default=True),
        ),
    ]
