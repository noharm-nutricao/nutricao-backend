import logging
from datetime import datetime, timezone

from decorators.has_permission_decorator import has_permission
from exception.validation_error import ValidationError
from repository.nutritional import nutritional_repository
from security.permission import Permission
from utils import status


@has_permission(Permission.READ_PRESCRIPTION)
def get_alertas(nratendimento: int) -> list[dict]:
    try:
        alertas = nutritional_repository.get_alertas(nratendimento)
        return [
            {
                "id": a.id,
                "tipo": a.tipo,
                "descricao": a.descricao,
                "severidade": a.severidade,
                "reconhecido": a.reconhecido or False,
                "reconhecido_at": a.reconhecido_at.isoformat() if a.reconhecido_at else None,
            }
            for a in alertas
        ]
    except Exception as e:
        logging.error(f"Erro ao buscar alertas do paciente {nratendimento}: {str(e)}")
        raise


