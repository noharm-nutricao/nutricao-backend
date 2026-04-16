import logging

from flask import Blueprint, request

from decorators.api_endpoint_decorator import api_endpoint

from services.nutritional import nutritional_patient_service
from services import patient_service
from routes.nutritional.validators.mnutric_validator import MnutricValidator

app_nutritional = Blueprint("app_nutritional", __name__)

APACHE_II_MIN = 0
SOFA_MIN = 0

@app_nutritional.route("/nutritional/patients", methods=["GET"])
@api_endpoint()
def get_patients():
    logging.info("Buscando lista de pacientes.")
    try:

        data = nutritional_patient_service.get_patients()

        if data is None:
            MnutricValidator.raise_invalid_manual_scores()

        logging.info(f"Busca de pacientes realizada com sucesso.")
        return data

    except Exception as e:
        logging.error(f"Falha na rota de pacientes: {str(e)}")
        return {"message": str(e)}, 500

@app_nutritional.route("/nutritional/patients/<int:nratendimento>/mnutric-manual", methods=["PUT"])
@api_endpoint()
def calculate_mnutric(nratendimento):
    data = request.get_json(silent=True) or {}

    apache = MnutricValidator.validate_required_manual_score(data, "apache_ii", APACHE_II_MIN)
    sofa   = MnutricValidator.validate_required_manual_score(data, "sofa", SOFA_MIN)

    patient = patient_service.get_patient_mnutric(nratendimento)
    mnutric = nutritional_patient_service.calculate_mnutric(patient, apache, sofa)

    return {
        "dados_incompletos": mnutric["dados_incompletos"],
        "mn_total": mnutric["total"],
        "mn_dims": {
            "idade" : mnutric["age"],
            "apache": mnutric["apache"],
            "sofa"  : mnutric["sofa"],
            "comor" : mnutric["comorbity"],
            "dias"  : mnutric["daysUTI"],
        },
        "classificacao": mnutric["classify"],
    }

