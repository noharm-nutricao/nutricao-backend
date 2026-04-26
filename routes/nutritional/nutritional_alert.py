import logging

from flask import Blueprint
from flask_jwt_extended import get_jwt_identity

from decorators.api_endpoint_decorator import api_endpoint
from services.nutritional import nutritional_alert_service

app_nutritional_alert = Blueprint("app_nutritional_alert", __name__)


@app_nutritional_alert.route(
    "/nutritional/patients/<int:nratendimento>/alertas", methods=["GET"]
)
@api_endpoint()
def get_alertas(nratendimento: int):
    logging.info(f"Buscando alertas do paciente {nratendimento}.")
    try:
        data = nutritional_alert_service.get_alertas(nratendimento)
        logging.info(f"Alertas do paciente {nratendimento} retornados com sucesso.")
        return data
    except Exception as e:
        logging.error(f"Falha ao buscar alertas: {str(e)}")
        raise



