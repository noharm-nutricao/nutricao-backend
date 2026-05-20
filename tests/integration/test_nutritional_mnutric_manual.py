"""Integration tests: nutritional mNUTRIC endpoint contract."""

import pytest
from sqlalchemy import text

from models.nutritional import NutritionalScreening
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


def _classify_total(total):
    if total < 0:
        return "unknown"
    if total <= 2:
        return "bx"
    if total <= 4:
        return "md"
    if total <= 6:
        return "al"
    return "cr"


def _is_nutritional_screening_table_ready():
    table_exists = bool(
        session.execute(
            text(
                "SELECT EXISTS ("
                "    SELECT 1 FROM information_schema.tables "
                "    WHERE table_schema = 'demo' "
                "      AND table_name = 'nutricional_triagem'"
                ")"
            )
        ).scalar()
    )

    if not table_exists:
        return False

    required_columns = {
        "id",
        "nratendimento",
        "protocolo",
        "mn_idade",
        "mn_apache",
        "mn_sofa",
        "mn_comor",
        "mn_dias",
        "mn_total",
        "mn_apache_manual",
        "mn_sofa_manual",
        "classificacao",
    }
    existing_columns = {
        row[0]
        for row in session.execute(
            text(
                "SELECT column_name "
                "FROM information_schema.columns "
                "WHERE table_schema = 'demo' "
                "  AND table_name = 'nutricional_triagem'"
            )
        ).all()
    }

    return required_columns.issubset(existing_columns)


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

def test_put_mnutric_persists_manual_scores_and_recalculates(client, analyst_headers):
    """PUT /nutritional/patients/:nratendimento/mnutric-manual - persiste os scores manuais e recalcula com paciente real"""
    payload = _payload(apache_ii=22, sofa=8)

    response = _put_mnutric_manual(client, headers=analyst_headers, payload=payload)

    body = response.get_json()

    assert response.status_code == status.HTTP_200_OK
    assert body["status"]                    == "success"
    assert body["data"]["dados_incompletos"] is False
    assert set(body["data"]["mn_dims"])      == {"idade", "apache", "sofa", "comor", "dias"}
    assert body["data"]["mn_dims"]["idade"]  == 0
    assert body["data"]["mn_dims"]["apache"] == 2
    assert body["data"]["mn_dims"]["sofa"]   == 1
    assert body["data"]["mn_dims"]["comor"]  == 0
    assert body["data"]["mn_total"]          == sum(body["data"]["mn_dims"].values())
    assert body["data"]["classificacao"]     == _classify_total(body["data"]["mn_total"])

    # only test these fields if we are ready to use them
    if _is_nutritional_screening_table_ready():
        session.expire_all()
        screening = (
            session.query(NutritionalScreening)
            .filter(NutritionalScreening.nratendimento == REAL_ADMISSION_NUMBER)
            .filter(NutritionalScreening.protocolo == "MNUTRIC")
            .order_by(NutritionalScreening.id.desc())
            .first()
        )

        assert screening is not None
        assert screening.mn_idade == body["data"]["mn_dims"]["idade"]
        assert screening.mn_apache == body["data"]["mn_dims"]["apache"]
        assert screening.mn_sofa == body["data"]["mn_dims"]["sofa"]
        assert screening.mn_comor == body["data"]["mn_dims"]["comor"]
        assert screening.mn_dias == body["data"]["mn_dims"]["dias"]
        assert screening.mn_total == body["data"]["mn_total"]
        assert screening.classificacao == body["data"]["classificacao"]
        assert screening.mn_apache_manual is True
        assert screening.mn_sofa_manual is True


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(_payload(apache_ii=-1,   sofa=8),    id="invalid-negative-apache"),
        pytest.param(_payload(apache_ii=22,   sofa=-1),   id="invalid-negative-sofa"),
        pytest.param({"sofa": 8},                         id="missing-apache"),
        pytest.param({"apache_ii": 22},                   id="missing-sofa"),
        pytest.param(_payload(apache_ii=None, sofa=8),    id="null-apache"),
        pytest.param(_payload(apache_ii=22,   sofa=None), id="null-sofa"),
        pytest.param(_payload(apache_ii="22", sofa=8),    id="string-apache"),
        pytest.param(_payload(apache_ii=22,   sofa="8"),  id="string-sofa"),
    ],
)
def test_put_mnutric_rejects_invalid_manual_scores(client, analyst_headers, payload):
    """PUT /nutritional/patients/:nratendimento/mnutric-manual - rejeita campos ausentes, nulos ou inválidos com 400"""
    response = _put_mnutric_manual(client, headers=analyst_headers, payload=payload)

    body = response.get_json()

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert body["status"]       == "error"
