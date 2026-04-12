from flask import Blueprint, request

# routes/nutritional/nutritional_patients.py
import logging

from flask import ( Blueprint, request ) 

from decorators.api_endpoint_decorator import api_endpoint
from decorators.has_permission_decorator import has_permission
from exception.validation_error import ValidationError
from security.permission import Permission

from services.nutritional import nutritional_patient_service
from services import patient_service
from utils import status

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

@app_nutritional.route("/nutritional/patients/<int:nratendimento>/mnutric-manual", methods=["PUT"])
@api_endpoint()
@has_permission(Permission.READ_PRESCRIPTION)
def calculate_mnutric(nratendimento):
    data = request.get_json(silent=True) or {}

    apache = _validate_required_manual_score(
        data,
        "apache_ii",
        APACHE_II_MIN,
    )
    sofa = _validate_required_manual_score(
        data,
        "sofa",
        SOFA_MIN,
    )
    patient = patient_service.get_patient_mnutric(nratendimento)

    mnutric = nutritional_patient_service.calculate_mnutric(patient, apache, sofa)

    return {
        "dados_incompletos": mnutric["dados_incompletos"],
        "mn_total": mnutric["total"],
        "mn_dims": {
            "idade": mnutric["age"],
            "apache": mnutric["apache"],
            "sofa": mnutric["sofa"],
            "comor": mnutric["comorbity"],
            "dias": mnutric["daysUTI"],
        },
        "classificacao": mnutric["classify"],
    }

def _raise_invalid_manual_scores():
    raise ValidationError(
        "Valores inválidos para APACHE II ou SOFA",
        "errors.invalidRequest",
        status.HTTP_400_BAD_REQUEST,
    )

def _validate_required_manual_score(data, field_name, minimum):
    if not isinstance(data, dict):
        _raise_invalid_manual_scores()

    if field_name not in data:
        _raise_invalid_manual_scores()

    value = data[field_name]

    if value is None:
        _raise_invalid_manual_scores()

    if isinstance(value, bool) or not isinstance(value, int):
        _raise_invalid_manual_scores()

    if value < minimum:
        _raise_invalid_manual_scores()

    return value
