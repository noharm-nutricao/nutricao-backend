
# routes/nutritional/nutritional_patients.py
from flask import Blueprint
from decorators.api_endpoint_decorator import api_endpoint
from decorators.has_permission_decorator import has_permission
from security.permission import Permission
from services.nutritional import nutritional_patient_service
import logging

app_nutritional = Blueprint("app_nutritional", __name__)

@app_nutritional.route("/nutritional/patients", methods=["GET"])
@api_endpoint()
@has_permission(Permission.READ_PRESCRIPTION)
def get_patients():
    logging.info("Buscando lista de pacientes.")
    try:

        data = nutritional_patient_service.get_patients()

        logging.info(f"Busca de pacientes realizada com sucesso.")

        return data, 200
    except Exception as e:
        logging.error(f"Falha na rota de pacientes: {str(e)}")
        return {"message": str(e)}, 500

