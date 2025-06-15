from rest_framework import mixins
import logging

logger = logging.getLogger(__name__)

class EmpresaFilterMixin(mixins.ListModelMixin):
    """
    Mixin para filtrar querysets por empresa.
    Adiciona automaticamente o filtro de empresa em todas as consultas
    e associa a empresa ao criar novos registros.
    """
    
    def get_queryset(self):
        queryset = super().get_queryset()
        empresa = getattr(self.request, 'empresa', None)
        if not empresa:
            logger.warning(f"[MIXIN] Nenhuma empresa encontrada para o usuário {self.request.user.email}")
            return queryset.none()
        logger.info(f"[MIXIN] Filtrando queryset por empresa: {empresa} (ID: {empresa.id}) para usuário: {self.request.user.email}")
        qs = queryset.filter(empresa=empresa)
        logger.info(f"[MIXIN] Queryset final count: {qs.count()} para empresa: {empresa} (ID: {empresa.id}) e usuário: {self.request.user.email}")
        return qs
    
    def perform_create(self, serializer):
        empresa = getattr(self.request, 'empresa', None)
        logger.warning(f"[MIXIN] Criando registro com empresa: {empresa} (ID: {getattr(empresa, 'id', None)})")
        if not empresa:
            logger.error(f"[MIXIN] Tentativa de criar registro sem empresa para o usuário {self.request.user.email}")
            raise ValueError("Empresa não encontrada. Por favor, selecione uma empresa primeiro.")
        serializer.save(empresa=empresa) 