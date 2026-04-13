from flask import Blueprint, request

from decorators.api_endpoint_decorator import api_endpoint
from models.requests.nrs_nut_request import NrsNutRequest
from services.nutritional import nrs_nut_service

app_nrs_nut = Blueprint("app_nrs_nut", __name__)


@app_nrs_nut.route(
    "/nutritional/patients/<int:nratendimento>/nrs-nut", methods=["PUT"]
)
@api_endpoint()
def update_nrs_nut(nratendimento):
    body = request.get_json(silent=True) or {}
    return nrs_nut_service.update_nrs_nut(
        nratendimento=nratendimento,
        request_data=NrsNutRequest(**body),
    )


