"""Route: nutritional patients listing endpoint."""

from flask import Blueprint, request

from decorators.api_endpoint_decorator import api_endpoint
from models.requests.nutritional_patients_request import NutritionalPatientsRequest
from services.nutritional import nutritional_active_patients_service

app_nutritional_active_patients = Blueprint("app_nutritional_active_patients", __name__)


@app_nutritional_active_patients.route("/nutritional/patients", methods=["GET"])
@api_endpoint(include_total=True)
def get_nutritional_patients():
    """GET /nutritional/patients - Returns active admissions with basic patient data.

    Each patient object includes ``freq_horas`` (integer or null) at the root level,
    derived from the latest assessment in ``nutricional_avaliacao.frequencia``:

    - ``12h`` -> 12, ``24h`` -> 24, ``48h`` -> 48, ``7d`` -> 168
    - ``rotina`` or no assessment -> null

    Example::

        {
            "id": 1001,
            "leito": "UTI-03",
            "haval": 20,
            "freq_horas": 24,
            ...
        }
    """
    return nutritional_active_patients_service.get_patients(
        request_data=NutritionalPatientsRequest(**request.args.to_dict(flat=True))
    )

