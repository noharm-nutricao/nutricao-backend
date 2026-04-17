"""Route: nutritional patients listing endpoint."""

from flask import Blueprint, request

from decorators.api_endpoint_decorator import api_endpoint
from models.requests.nutritional_patients_request import NutritionalPatientsRequest
from services.nutritional import nutritional_active_patients_service

app_nutritional_active_patients = Blueprint("app_nutritional_active_patients", __name__)


@app_nutritional_active_patients.route("/nutritional/patients", methods=["GET"])
@api_endpoint(include_total=True)
def get_nutritional_patients():
    """GET /nutritional/patients - Returns active admissions with basic patient data."""
    return nutritional_active_patients_service.get_patients(
        request_data=NutritionalPatientsRequest(**request.args.to_dict(flat=True))
    )

