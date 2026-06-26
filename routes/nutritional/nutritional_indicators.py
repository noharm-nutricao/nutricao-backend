"""Route for GET /nutritional/indicators."""

from flask import Blueprint, request

from decorators.api_endpoint_decorator import api_endpoint
from models.requests.nutritional_indicators_request import NutritionalIndicatorsRequest
from services.nutritional import nutritional_indicators_service

app_nutritional_indicators = Blueprint("app_nutritional_indicators", __name__)


@app_nutritional_indicators.route("/nutritional/indicators", methods=["GET"])
@api_endpoint()
def get_indicators():
    return nutritional_indicators_service.get_indicators(
        request_data=NutritionalIndicatorsRequest(**request.args.to_dict(flat=True))
    )
