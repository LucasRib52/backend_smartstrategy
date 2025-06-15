# Guia de Contribuição

## 🛡️ Regra de Ouro: Isolamento Multiempresa

Todo modelo que contém dados de uma empresa **deve obrigatoriamente**:

1. Ter o campo `empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE)`
2. Usar a `EmpresaFilterMixin` na view correspondente para:
   - Filtrar automaticamente os dados pela empresa ativa (`request.empresa`)
   - Associar a empresa ao criar registros
3. Ser testado com múltiplos usuários PJ para evitar vazamento de dados entre empresas

### Exemplos

#### Modelo
```python
from empresas.models import Empresa

class Produto(models.Model):
    nome = models.CharField(max_length=100)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='produtos')
```

#### View
```python
from empresas.mixins import EmpresaFilterMixin
from rest_framework import viewsets

class ProdutoViewSet(EmpresaFilterMixin, viewsets.ModelViewSet):
    queryset = Produto.objects.all()
    serializer_class = ProdutoSerializer
```

### Por que seguir esta regra?

1. **Consistência**: Garante que todos os dados sensíveis estejam vinculados à empresa correta
2. **Segurança**: Previne vazamento de dados entre empresas
3. **Manutenibilidade**: Facilita a manutenção e evolução do sistema
4. **Performance**: Otimiza queries e joins no banco de dados

### Testes Recomendados

Ao implementar um novo modelo que segue esta regra, teste:

1. Criar registros com diferentes empresas
2. Verificar se cada empresa vê apenas seus próprios dados
3. Confirmar que o `empresa_id` está sendo salvo corretamente no banco
4. Validar que o `EmpresaFilterMixin` está filtrando corretamente as listagens 