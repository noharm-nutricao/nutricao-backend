import logging

from flask import Blueprint

from decorators.api_endpoint_decorator import api_endpoint
from services.nutritional import nutritional_alert_service

app_nutritional_alert = Blueprint("app_nutritional_alert", __name__)


@app_nutritional_alert.route(
    "/nutritional/patients/<int:nratendimento>/alerts", methods=["GET"]
)
@api_endpoint()
def get_alerts(nratendimento: int):
    logging.info(f"Buscando alertas do paciente {nratendimento}.")
    try:
        data = nutritional_alert_service.get_alerts(nratendimento)
        logging.info(f"Alertas do paciente {nratendimento} retornados com sucesso.")
        return data
    except Exception as e:
        logging.error(f"Falha ao buscar alertas: {str(e)}")
        raise


@app_nutritional_alert.route(
    "/nutritional/patients/<int:nratendimento>/alerts/<int:alert_id>/acknowledge",
    methods=["POST"],
)
@api_endpoint()
def acknowledge_alerta(nratendimento: int, alert_id: int, user_context):
    logging.info(f"Reconhecendo alerta {alert_id} do paciente {nratendimento}.")
    try:
        data = nutritional_alert_service.acknowledge_alert(
            nratendimento=nratendimento,
            alert_id=alert_id,
            user_context=user_context,
        )
        logging.info(
            f"Alerta {alert_id} do paciente {nratendimento} reconhecido com sucesso."
        )
        return data
    except Exception as e:
        logging.error(f"Falha ao reconhecer alerta: {str(e)}")
        raise
