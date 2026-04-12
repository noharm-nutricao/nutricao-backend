
# routes/nutritional/nutritional_patients.py
import logging

from flask import ( Blueprint, request ) 

from decorators.api_endpoint_decorator import api_endpoint
from exception.validation_error import ValidationErrorfrom 
from utils import status

from services.nutritional import nutritional_patient_service
from services import patient_service
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

@app_nutritional.route("/nutritional/patients/<int:nratendimento>/mnutric", methods=["PUT"])
@api_endpoint()
@has_permission(Permission.READ_PRESCRIPTION)
def calculate_mnutric(nratendimento):
    try:
        data = request.get_json()

        apache  = data.get("apache_ii", None)
        sofa    = data.get("sofa", None)        
        patient = patient_service.get_patient_mnutric(nratendimento)

        mnutric = nutritional_patient_service.calculate_mnutric(patient, apache, sofa)

        response = {
                "dados_incompletos": False,
                "mn_total": mnutric["total"],
                "mn_dims": {
                        "idade": mnutric["age"], 
                        "apache": mnutric["apache"], 
                        "sofa": mnutric["sofa"], 
                        "comor": mnutric["comorbity"], 
                        "dias": mnutric["daysUTI"]
                    },
                "classificacao": mnutric["classify"]
            }

        return response, status.HTTP_200_OK
    except:
        return {"message": "error"}, status.HTTP_500_INTERNAL_SERVER_ERROR
