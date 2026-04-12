"""Integration tests: nutritional mNUTRIC endpoint contract."""

from unittest.mock import patch

import pytest

from exception.validation_error import ValidationError
from utils import status

CURRENT_ENDPOINT = "/nutritional/patients/123456/mnutric"


def _payload(apache_ii=22, sofa=8):
    return {"apache_ii": apache_ii, "sofa": sofa}


def _put_mnutric(client, headers=None, payload=None):
    return client.put(
        CURRENT_ENDPOINT,
        headers=headers,
        json=payload or _payload(),
    )


def _success_result():
    return {
        "total": 7,
        "age": 2,
        "apache": 2,
        "sofa": 1,
        "comorbity": 1,
        "daysUTI": 1,
        "classify": "cr",
        "dados_incompletos": False,
    }


def _incomplete_result():
    return {
        "total": 0,
        "age": 0,
        "apache": None,
        "sofa": None,
        "comorbity": 0,
        "daysUTI": 0,
        "classify": None,
        "dados_incompletos": True,
    }


def _expected_response_data(result, dados_incompletos):
    return {
        "dados_incompletos": dados_incompletos,
        "mn_total": result["total"],
        "mn_dims": {
            "idade": result["age"],
            "apache": result["apache"],
            "sofa": result["sofa"],
            "comor": result["comorbity"],
            "dias": result["daysUTI"],
        },
        "classificacao": result["classify"],
    }


@pytest.mark.parametrize(
    "headers_fixture_name",
    [
        pytest.param(None, id="without-token")
    ],
)
def test_put_mnutric_requires_authorization(client, request, headers_fixture_name):
    """PUT /nutritional/patients/:nratendimento/mnutric - sem autenticação/permissão deve retornar 401"""
    headers = (
        request.getfixturevalue(headers_fixture_name)
        if headers_fixture_name is not None
        else None
    )

    response = _put_mnutric(client, headers=headers)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.parametrize(
    ("service_result", "payload", "expected_data"),
    [
        pytest.param(
            _success_result(),
            _payload(),
            _expected_response_data(_success_result(), False),
            id="complete-result",
        ),
        pytest.param(
            _incomplete_result(),
            _payload(apache_ii=None),
            _expected_response_data(_incomplete_result(), True),
            id="incomplete-apache-result",
        ),
        pytest.param(
            _incomplete_result(),
            _payload(sofa=None),
            _expected_response_data(_incomplete_result(), True),
            id="incomplete-sofa-result",
        ),
        pytest.param(
            _incomplete_result(),
            _payload(apache_ii=None, sofa=None),
            _expected_response_data(_incomplete_result(), True),
            id="incomplete-result",
        ),
    ],
)
def test_put_mnutric_returns_expected_payload(
    client,
    analyst_headers,
    service_result,
    payload,
    expected_data,
):
    """PUT /nutritional/patients/:nratendimento/mnutric - retorna payload esperado para cenários de sucesso"""
    with patch(
        "routes.nutritional.nutritional_patients.patient_service.get_patient_mnutric",
        return_value=object(),
    ), patch(
        "routes.nutritional.nutritional_patients.nutritional_patient_service.calculate_mnutric",
        return_value=service_result,
    ):
        response = _put_mnutric(client, headers=analyst_headers, payload=payload)

    body = response.get_json()

    assert response.status_code == status.HTTP_200_OK
    assert body["status"] == "success"
    assert body["data"] == expected_data


@pytest.mark.parametrize(
    ("raise_from", "payload", "exception", "expected_status"),
    [
        pytest.param(
            "calculate",
            _payload(apache_ii=-1, sofa=8),
            ValidationError(
                "Valores inválidos para APACHE II ou SOFA",
                "errors.invalidRequest",
                status.HTTP_400_BAD_REQUEST,
            ),
            status.HTTP_400_BAD_REQUEST,
            id="invalid-score",
        ),
        pytest.param(
            "patient",
            _payload(),
            ValidationError(
                "Paciente não é de UTI",
                "errors.businessRules",
                422,
            ),
            422,
            id="non-icu-patient",
        ),
    ],
)
def test_put_mnutric_rejects_invalid_processes(
    client,
    analyst_headers,
    raise_from,
    payload,
    exception,
    expected_status,
):
    """PUT /nutritional/patients/:nratendimento/mnutric - retorna erro esperado para cenários inválidos"""
    patient_patch_kwargs = (
        {"side_effect": exception}
        if raise_from == "patient"
        else {"return_value": object()}
    )
    calculate_patch_kwargs = (
        {"side_effect": exception}
        if raise_from == "calculate"
        else {"return_value": _success_result()}
    )

    with patch(
        "routes.nutritional.nutritional_patients.patient_service.get_patient_mnutric",
        **patient_patch_kwargs,
    ), patch(
        "routes.nutritional.nutritional_patients.nutritional_patient_service.calculate_mnutric",
        **calculate_patch_kwargs,
    ):
        response = _put_mnutric(client, headers=analyst_headers, payload=payload)

    body = response.get_json()

    assert response.status_code == expected_status
    assert body["status"] == "error"
