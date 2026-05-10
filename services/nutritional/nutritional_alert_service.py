import logging

from decorators.has_permission_decorator import has_permission
from exception.validation_error import ValidationError
from models.main import User
from repository.nutritional import nutritional_repository
from security.permission import Permission
from utils import status
from utils.dateutils import now_sp


@has_permission(Permission.READ_PRESCRIPTION)
def get_alerts(nratendimento: int) -> list[dict]:
    try:
        alerts = nutritional_repository.get_alertas(nratendimento)
        return [
            {
                "id": a.id,
                "tipo": a.tipo,
                "descricao": a.descricao,
                "severidade": a.severidade,
                "reconhecido": a.reconhecido or False,
                "reconhecido_at": a.reconhecido_at.isoformat() if a.reconhecido_at else None,
            }
            for a in alerts
        ]
    except Exception as e:
        logging.error(f"Erro ao buscar alertas do paciente {nratendimento}: {str(e)}")
        raise


@has_permission(Permission.WRITE_NUTRITIONAL)
def acknowledge_alert(nratendimento: int, alert_id: int, user_context: User):
    logging.error(f"Buscando paciente {nratendimento}, alerta {alert_id}")
    alert = nutritional_repository.get_alerta(nratendimento, alert_id)
    logging.error(f"Encontrado {alert}")

    if alert is None or not alert.ativo:
        raise ValidationError(
            "Alerta não encontrado ou inativo",
            "errors.notFound",
            status.HTTP_404_NOT_FOUND,
        )

    if alert.reconhecido:
        raise ValidationError(
            "Alerta já foi reconhecido",
            "errors.conflict",
            status.HTTP_409_CONFLICT,
        )

    reconhecido_at = now_sp()
    alert.reconhecido = True
    alert.reconhecido_por = user_context.id
    alert.reconhecido_at = reconhecido_at

    return {
        "id": alert.id,
        "reconhecido": True,
        "reconhecido_at": reconhecido_at.isoformat(),
    }
