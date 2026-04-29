import logging

from decorators.has_permission_decorator import has_permission
from exception.validation_error import ValidationError
from models.main import User
from repository.nutritional import nutritional_repository
from security.permission import Permission
from utils import status
from utils.dateutils import now_sp


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


@has_permission(Permission.WRITE_NUTRITIONAL)
def acknowledge_alerta(nratendimento: int, alerta_id: int, user_context: User):
    alerta = nutritional_repository.get_alerta(nratendimento, alerta_id)

    if alerta is None or not alerta.ativo:
        raise ValidationError(
            "Alerta não encontrado ou inativo",
            "errors.notFound",
            status.HTTP_404_NOT_FOUND,
        )

    if alerta.reconhecido:
        raise ValidationError(
            "Alerta já foi reconhecido",
            "errors.conflict",
            status.HTTP_409_CONFLICT,
        )

    reconhecido_at = now_sp()
    alerta.reconhecido = True
    alerta.reconhecido_por = user_context.id
    alerta.reconhecido_at = reconhecido_at

    return {
        "id": alerta.id,
        "reconhecido": True,
        "reconhecido_at": reconhecido_at.isoformat(),
    }
