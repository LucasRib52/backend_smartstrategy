from django import forms
from .models import Venda
from .utils import obter_clima

class VendaForm(forms.ModelForm):
    class Meta:
        model = Venda
        exclude = ['clima']

        widgets = {
            'data': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'mes': forms.TextInput(attrs={'class': 'form-control'}),
            'ano': forms.NumberInput(attrs={'class': 'form-control'}),
            'semana': forms.TextInput(attrs={'class': 'form-control'}),

            'invest_realizado': forms.NumberInput(attrs={'class': 'form-control'}),
            'invest_projetado': forms.NumberInput(attrs={'class': 'form-control'}),
            'saldo_invest': forms.NumberInput(attrs={'class': 'form-control'}),

            'vendas_google': forms.NumberInput(attrs={'class': 'form-control'}),
            'vendas_instagram': forms.NumberInput(attrs={'class': 'form-control'}),
            'vendas_facebook': forms.NumberInput(attrs={'class': 'form-control'}),

            'fat_proj': forms.NumberInput(attrs={'class': 'form-control'}),
            'fat_camp_realizado': forms.NumberInput(attrs={'class': 'form-control'}),
            'fat_geral': forms.NumberInput(attrs={'class': 'form-control'}),
            'saldo_fat': forms.NumberInput(attrs={'class': 'form-control'}),

            'roi_realizado': forms.NumberInput(attrs={'class': 'form-control'}),
            'roas_realizado': forms.NumberInput(attrs={'class': 'form-control'}),
            'cac_realizado': forms.NumberInput(attrs={'class': 'form-control'}),

            'ticket_medio_realizado': forms.NumberInput(attrs={'class': 'form-control'}),
            'arpu_realizado': forms.NumberInput(attrs={'class': 'form-control'}),

            'clientes_novos': forms.NumberInput(attrs={'class': 'form-control'}),
            'clientes_recorrentes': forms.NumberInput(attrs={'class': 'form-control'}),
            
            'leads': forms.NumberInput(attrs={'class': 'form-control'}),
            
            'conversoes': forms.NumberInput(attrs={'class': 'form-control'}),

            'taxa_conversao': forms.NumberInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        readonly_fields = [
            'mes', 'ano', 'semana',
            'saldo_invest', 'saldo_fat',
            'roi_realizado', 'roas_realizado',
            'cac_realizado', 'arpu_realizado',
            'taxa_conversao'
        ]

        for field in readonly_fields:
            if field in self.fields:
                self.fields[field].widget.attrs['readonly'] = True
                self.fields[field].widget.attrs['style'] = (
                    'background-color: #f4f4f4; color: #6c757d; cursor: not-allowed;'
                )

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.clima = obter_clima()
        if commit:
            instance.save()
        return instance
