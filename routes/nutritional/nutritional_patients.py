
# routes/nutritional/nutritional_patients.py
from flask import Blueprint
from decorators.api_endpoint_decorator import api_endpoint
from decorators.has_permission_decorator import has_permission
from security.permission import Permission

from services.nutritional import nutritional_patient_service

app_nutritional = Blueprint("app_nutritional", __name__)

@app_nutritional.route("/nutritional/patients", methods=["GET"])
@api_endpoint()
@has_permission(Permission.READ_PRESCRIPTION)
def get_patients():
    return nutritional_patient_service.get_patients()
