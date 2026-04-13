"""Integration tests: nutritional mNUTRIC endpoint contract."""

from unittest.mock import patch

import pytest
from sqlalchemy import text

from exception.validation_error import ValidationError
from models.nutritional.nutritional import NutritionalTriage
from tests.conftest import session
from utils import status

REAL_ADMISSION_NUMBER = 1
CURRENT_ENDPOINT = f"/nutritional/patients/{REAL_ADMISSION_NUMBER}/mnutric-manual"


def _payload(apache_ii=22, sofa=8):
    return {"apache_ii": apache_ii, "sofa": sofa}


def _put_mnutric_manual(client, headers=None, payload=None):
    return client.put(
        CURRENT_ENDPOINT,
        headers=headers,
        json=_payload() if payload is None else payload,
    )


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
    """PUT /nutritional/patients/:nratendimento/mnutric-manual - sem autenticação/permissão deve retornar 401"""
    headers = (
        request.getfixturevalue(headers_fixture_name)
        if headers_fixture_name is not None
        else None
    )

    response = _put_mnutric_manual(client, headers=headers)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def _cleanup_manual_triage(admission_number):
    session.execute(
        text(
            "DO $$ "
            "BEGIN "
            "IF EXISTS ("
            "    SELECT 1 FROM information_schema.tables "
            "    WHERE table_schema = 'demo' AND table_name = 'nutricional_triagem'"
            ") THEN "
            "    DELETE FROM demo.nutricional_triagem WHERE nratendimento = :admission_number; "
            "END IF; "
            "END $$;"
        ),
        {"admission_number": admission_number},
    )
    session.commit()
    session.connection(execution_options={"schema_translate_map": {None: "demo"}})


def test_put_mnutric_persists_manual_scores_and_recalculates(client, analyst_headers):
    """PUT /nutritional/patients/:nratendimento/mnutric-manual - persiste os scores manuais e recalcula com paciente real"""
    payload = _payload(apache_ii=22, sofa=8)

    _cleanup_manual_triage(REAL_ADMISSION_NUMBER)

    response = _put_mnutric_manual(client, headers=analyst_headers, payload=payload)

    body = response.get_json()

    assert response.status_code == status.HTTP_200_OK
    assert body["status"] == "success"
    assert body["data"] == {
        "dados_incompletos": False,
        "mn_total": 4,
        "mn_dims": {
            "idade": 0,
            "apache": 2,
            "sofa": 1,
            "comor": 0,
            "dias": 1,
        },
        "classificacao": "md",
    }

    session.expire_all()
    triage = (
        session.query(NutritionalTriage)
        .filter(NutritionalTriage.admissionNumber == REAL_ADMISSION_NUMBER)
        .first()
    )

    assert triage is not None
    assert triage.apache == payload["apache_ii"]
    assert triage.sofa == payload["sofa"]
    assert triage.total == body["data"]["mn_total"]
    assert triage.apacheManual is True
    assert triage.sofaManual is True


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(_payload(apache_ii=-1, sofa=8), id="invalid-negative-apache"),
        pytest.param(_payload(apache_ii=22, sofa=-1), id="invalid-negative-sofa"),
        pytest.param({"sofa": 8}, id="missing-apache"),
        pytest.param({"apache_ii": 22}, id="missing-sofa"),
        pytest.param(_payload(apache_ii=None, sofa=8), id="null-apache"),
        pytest.param(_payload(apache_ii=22, sofa=None), id="null-sofa"),
        pytest.param(_payload(apache_ii="22", sofa=8), id="string-apache"),
        pytest.param(_payload(apache_ii=22, sofa="8"), id="string-sofa"),
    ],
)
def test_put_mnutric_rejects_invalid_manual_scores(client, analyst_headers, payload):
    """PUT /nutritional/patients/:nratendimento/mnutric-manual - rejeita campos ausentes, nulos ou inválidos com 400"""
    with patch(
        "routes.nutritional.nutritional_patients.patient_service.get_patient_mnutric"
    ) as get_patient_mock, patch(
        "routes.nutritional.nutritional_patients.nutritional_patient_service.calculate_mnutric"
    ) as calculate_mock:
        response = _put_mnutric_manual(client, headers=analyst_headers, payload=payload)

    body = response.get_json()

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert body["status"] == "error"
    assert body["message"] == "Valores inválidos para APACHE II ou SOFA"
    assert body["code"] == "errors.invalidRequest"
    get_patient_mock.assert_not_called()
    calculate_mock.assert_not_called()


@pytest.mark.parametrize(
    ("raise_from", "payload", "exception", "expected_status"),
    [
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
    """PUT /nutritional/patients/:nratendimento/mnutric-manual - retorna erro esperado para cenários inválidos"""
    patient_patch_kwargs = (
        {"side_effect": exception}
        if raise_from == "patient"
        else {"return_value": object()}
    )
    calculate_patch_kwargs = (
        {"side_effect": exception}
        if raise_from == "calculate"
        else {"return_value": {"dados_incompletos": False}}
    )

    with patch(
        "routes.nutritional.nutritional_patients.patient_service.get_patient_mnutric",
        **patient_patch_kwargs,
    ), patch(
        "routes.nutritional.nutritional_patients.nutritional_patient_service.calculate_mnutric",
        **calculate_patch_kwargs,
    ):
        response = _put_mnutric_manual(client, headers=analyst_headers, payload=payload)

    body = response.get_json()

    assert response.status_code == expected_status
    assert body["status"] == "error"
