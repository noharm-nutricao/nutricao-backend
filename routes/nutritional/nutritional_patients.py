
# routes/nutritional/nutritional_patients.py
import logging

from flask import Blueprint

from decorators.api_endpoint_decorator import api_endpoint
from exception.validation_error import ValidationError
from services.nutritional import nutritional_patient_service
from utils import status

app_nutritional = Blueprint("app_nutritional", __name__)

@app_nutritional.route("/nutritional/patients", methods=["GET"])
@api_endpoint()
def get_patients():
    logging.info("Buscando lista de pacientes.")
    try:

        data = nutritional_patient_service.get_patients()

        if data is None:
            raise ValidationError(
                "Nenhum paciente encontrado.",
                "errors.notFound",
                status.HTTP_404_NOT_FOUND
            )

        logging.info(f"Busca de pacientes realizada com sucesso.")
        return data

    except Exception as e:
        logging.error(f"Falha na rota de pacientes: {str(e)}")
        return {"message": str(e)}, 500

