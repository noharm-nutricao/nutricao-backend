from typing import Any

from flask import Blueprint, Request, request

from decorators.api_endpoint_decorator import api_endpoint
from models.requests.nutritional_llm_request import NutritionalLlmSummaryRequest
from services.nutritional import nutritional_llm_synchronus_service

app_nutritional_llm: Blueprint = Blueprint("app_nutritional_llm", __name__)


@app_nutritional_llm.route(
    "/nutritional/patients/<int:nratendimento>/llm-summary-synchronous",
    methods=["POST"],
)
@api_endpoint()
def generate_llm_summary_synchronous(nratendimento: int, user_context: Any):
    data: Request = request.get_json(silent=True) or {}

    payload = NutritionalLlmSummaryRequest(**data)

    return nutritional_llm_synchronus_service.generate_summary(
        nratendimento=nratendimento,
        request_data=payload,
        user_context=user_context,
    )
