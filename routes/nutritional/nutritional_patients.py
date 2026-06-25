import logging

from flask import Blueprint, request

from decorators.api_endpoint_decorator import api_endpoint
from models.requests.nutritional_assessment_request import NutritionalAssessmentRequest
from models.requests.nutritional_glim_request import NutritionalGlimRequest
from repository.nutritional import nutritional_nrs_repository

from services.nutritional import nutritional_patient_service
from services import patient_service
from routes.nutritional.validators.mnutric_validator import MnutricValidator

app_nutritional = Blueprint("app_nutritional", __name__)

APACHE_II_MIN = 0
SOFA_MIN = 0

@app_nutritional.route("/nutritional/list/patients", methods=["GET"])
@api_endpoint()
def get_patients():
    logging.info("Buscando lista de pacientes.")
    try:

        data = nutritional_patient_service.get_patients()

        # if data is None:
        #     MnutricValidator.raise_invalid_manual_scores()

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

@app_nutritional.route("/nutritional/patients/<int:nratendimento>", methods=["GET"])
@api_endpoint()
def list_patients_with_campo1(nratendimento):
    return nutritional_patient_service.get_patients_by_nra(nratendimento)


@app_nutritional.route(
    "/nutritional/patients/<int:nratendimento>/assessments",
    methods=["POST"]
)
@api_endpoint()
def create_assessment(nratendimento: int, user_context):
    data = request.get_json(silent=True) or {}

    payload = NutritionalAssessmentRequest(**data)

    return nutritional_patient_service.create_assessment(
        nratendimento=nratendimento,
        data=payload,
        idusuario=user_context.id
    )


@app_nutritional.route(
    "/nutritional/patients/<int:nratendimento>/assessments",
    methods=["GET"]
)
@api_endpoint()
def list_assessments(nratendimento: int):
    limit = request.args.get("limit", 10, type=int)

    return nutritional_patient_service.get_assessments(
        nratendimento=nratendimento,
        limit=limit
    )


@app_nutritional.route(
    "/nutritional/patients/<int:nratendimento>/glim",
    methods=["POST"]
)
@api_endpoint()
def save_glim(nratendimento: int, user_context):
    data = request.get_json(silent=True) or {}

    payload = NutritionalGlimRequest(**data)

    return nutritional_patient_service.save_glim(
        nratendimento=nratendimento,
        data=payload,
        idusuario=user_context.id
    )


@app_nutritional.route(
    "/nutritional/patients/<int:nratendimento>/glim",
    methods=["GET"]
)
@api_endpoint()
def get_glim(nratendimento: int):
    return nutritional_patient_service.get_glim(nratendimento=nratendimento)


@app_nutritional.route("/nutritional/patients/<int:nratendimento>/d7", methods=["POST"])
@api_endpoint()
def create_d7(nratendimento):
    return nutritional_patient_service.create_d7(nratendimento=nratendimento)


@app_nutritional.route("/nutritional/patients/<int:nratendimento>/d7", methods=["GET"])
@api_endpoint()
def get_d7(nratendimento):
    return nutritional_patient_service.get_d7(nratendimento=nratendimento)


@app_nutritional.route(
    "/nutritional/patients/<int:nratendimento>/d7/<int:id>/close", methods=["PUT"]
)
@api_endpoint()
def close_d7(nratendimento, id):
    return nutritional_patient_service.close_d7(nratendimento=nratendimento, id=id)
