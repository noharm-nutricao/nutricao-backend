"""Integration tests: nutritional assessment endpoints contract."""

import pytest
from sqlalchemy import text

from security.role import Role
from tests.conftest import get_access, make_headers, session, session_commit

_HOSPITAL = 1
_ADM = 920001
_ADM_NOT_FOUND = 999997

_POST_ENDPOINT = f"/nutritional/patients/{_ADM}/assessments"
_GET_ENDPOINT = f"/nutritional/patients/{_ADM}/assessments"

_REQUIRED_COLUMNS = {
    "pessoa": {"fkpessoa", "fkhospital", "nratendimento", "dtinternacao"},
    "nutricional_avaliacao": {
        "id",
        "nratendimento",
        "idusuario",
        "conduta",
        "frequencia",
        "ingestao",
        "meta_kcal",
        "meta_prot",
        "created_at",
    },
    "nutricional_d7": {
        "id",
        "nratendimento",
        "dt_prevista",
        "concluido",
        "idusuario",
        "created_at",
        "updated_at",
    },
}


@pytest.fixture(scope="module", autouse=True)
def setup_assessment_module():
    _ensure_schema()
    _cleanup()
    _seed()
    yield
    _cleanup()


@pytest.fixture()
def analyst_headers(client):
    return make_headers(get_access(client, roles=[Role.PRESCRIPTION_ANALYST.value]))


@pytest.fixture()
def viewer_headers(client):
    return make_headers(get_access(client, roles=[Role.VIEWER.value]))


# ---------------------------------------------------------------------------
# Setup helpers
# ---------------------------------------------------------------------------


def _ensure_schema():
    missing = []

    for table_name, required_columns in _REQUIRED_COLUMNS.items():
        existing_columns = {
            row.column_name
            for row in session.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema = 'demo' AND table_name = :t"
                ),
                {"t": table_name},
            ).fetchall()
        }

        if not existing_columns:
            missing.append(f"demo.{table_name} table")
            continue

        for col in sorted(required_columns - existing_columns):
            missing.append(f"demo.{table_name}.{col}")

    if missing:
        pytest.fail(
            "Test database schema not ready for assessment tests. Missing: "
            + ", ".join(missing),
            pytrace=False,
        )


def _seed():
    session.execute(
        text(
            "INSERT INTO demo.pessoa "
            "(fkpessoa, fkhospital, nratendimento, dtinternacao) "
            "VALUES (:pk, :hosp, :adm, NOW() - INTERVAL '5 days') "
            "ON CONFLICT DO NOTHING"
        ),
        {"pk": _ADM, "hosp": _HOSPITAL, "adm": _ADM},
    )
    session_commit()


def _cleanup():
    session.execute(text("DELETE FROM demo.nutricional_triagem WHERE nratendimento >= 920000"))
    session.execute(text("DELETE FROM demo.nutricional_alerta WHERE nratendimento >= 920000"))
    session.execute(text("DELETE FROM demo.nutricional_nrs WHERE nratendimento >= 920000"))
    session.execute(text("DELETE FROM demo.nutricional_glim WHERE nratendimento >= 920000"))
    session.execute(text("DELETE FROM demo.nutricional_d7 WHERE nratendimento >= 920000"))
    session.execute(text("DELETE FROM demo.nutricional_avaliacao WHERE nratendimento >= 920000"))
    session.execute(text("DELETE FROM demo.pessoa WHERE nratendimento >= 920000"))
    session_commit()


def _cleanup_assessments():
    session.execute(
        text("DELETE FROM demo.nutricional_avaliacao WHERE nratendimento = :adm"),
        {"adm": _ADM},
    )
    session.execute(
        text("DELETE FROM demo.nutricional_d7 WHERE nratendimento = :adm"),
        {"adm": _ADM},
    )
    session_commit()


def _payload(**overrides):
    payload = {
        "conduta": "Dieta hipercalorica hipoproteica",
        "prox_visita": "24h",
        "ingestao": 70,
        "meta_kcal": 1800,
        "meta_prot": 80,
    }
    payload.update(overrides)
    return payload


def _count_assessments():
    return session.execute(
        text("SELECT COUNT(*) FROM demo.nutricional_avaliacao WHERE nratendimento = :adm"),
        {"adm": _ADM},
    ).scalar()


def _count_active_d7():
    return session.execute(
        text(
            "SELECT COUNT(*) FROM demo.nutricional_d7 "
            "WHERE nratendimento = :adm AND concluido = false"
        ),
        {"adm": _ADM},
    ).scalar()


# ---------------------------------------------------------------------------
# POST /nutritional/patients/:nratendimento/assessments
# ---------------------------------------------------------------------------


def test_post_assessment_requires_authorization(client):
    response = client.post(_POST_ENDPOINT, json=_payload())
    assert response.status_code == 401


def test_post_assessment_requires_write_nutritional_permission(client, viewer_headers):
    response = client.post(_POST_ENDPOINT, json=_payload(), headers=viewer_headers)
    assert response.status_code == 401


def test_post_assessment_creates_successfully(client, analyst_headers):
    _cleanup_assessments()

    response = client.post(_POST_ENDPOINT, json=_payload(), headers=analyst_headers)

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "success"
    data = body["data"]
    assert data["id"] is not None
    assert data["conduta"] == "Dieta hipercalorica hipoproteica"
    assert data["ingestao"] == 70
    assert data["meta_kcal"] == 1800
    assert data["meta_prot"] == 80
    assert data["created_at"] is not None


def test_post_assessment_persists_in_db(client, analyst_headers):
    _cleanup_assessments()

    client.post(_POST_ENDPOINT, json=_payload(), headers=analyst_headers)

    session.expire_all()
    assert _count_assessments() == 1


def test_post_assessment_returns_404_for_nonexistent_patient(client, analyst_headers):
    endpoint = f"/nutritional/patients/{_ADM_NOT_FOUND}/assessments"
    response = client.post(endpoint, json=_payload(), headers=analyst_headers)

    assert response.status_code == 404
    assert response.get_json()["code"] == "errors.notFound"


def test_post_assessment_with_d7_prox_visita_creates_d7(client, analyst_headers):
    _cleanup_assessments()

    response = client.post(
        _POST_ENDPOINT,
        json=_payload(prox_visita="D7"),
        headers=analyst_headers,
    )

    assert response.status_code == 200

    session.expire_all()
    assert _count_assessments() == 1
    assert _count_active_d7() == 1


def test_post_assessment_with_d7_closes_existing_active_d7(client, analyst_headers):
    _cleanup_assessments()
    # create an existing active D7
    session.execute(
        text(
            "INSERT INTO demo.nutricional_d7 "
            "(nratendimento, dt_prevista, concluido, created_at) "
            "VALUES (:adm, NOW() + INTERVAL '7 days', false, NOW())"
        ),
        {"adm": _ADM},
    )
    session_commit()
    assert _count_active_d7() == 1

    client.post(
        _POST_ENDPOINT,
        json=_payload(prox_visita="D7"),
        headers=analyst_headers,
    )

    session.expire_all()
    # old d7 closed, new one created → still 1 active
    assert _count_active_d7() == 1
    total_d7 = session.execute(
        text("SELECT COUNT(*) FROM demo.nutricional_d7 WHERE nratendimento = :adm"),
        {"adm": _ADM},
    ).scalar()
    assert total_d7 == 2


def test_post_assessment_non_d7_prox_visita_does_not_create_d7(client, analyst_headers):
    _cleanup_assessments()

    client.post(_POST_ENDPOINT, json=_payload(prox_visita="48h"), headers=analyst_headers)

    session.expire_all()
    assert _count_active_d7() == 0


def test_post_assessment_prox_visita_frequencia_mapping(client, analyst_headers):
    _cleanup_assessments()

    response = client.post(
        _POST_ENDPOINT,
        json=_payload(prox_visita="D7"),
        headers=analyst_headers,
    )

    data = response.get_json()["data"]
    assert data["prox_visita"] == "7d"


def test_post_assessment_rejects_empty_conduta(client, analyst_headers):
    response = client.post(
        _POST_ENDPOINT,
        json=_payload(conduta=""),
        headers=analyst_headers,
    )

    assert response.status_code == 400


def test_post_assessment_rejects_invalid_prox_visita(client, analyst_headers):
    response = client.post(
        _POST_ENDPOINT,
        json=_payload(prox_visita="amanha"),
        headers=analyst_headers,
    )

    assert response.status_code == 400


def test_post_assessment_rejects_ingestao_out_of_range(client, analyst_headers):
    response = client.post(
        _POST_ENDPOINT,
        json=_payload(ingestao=150),
        headers=analyst_headers,
    )

    assert response.status_code == 400


# ---------------------------------------------------------------------------
# GET /nutritional/patients/:nratendimento/assessments
# ---------------------------------------------------------------------------


def test_get_assessments_requires_authorization(client):
    response = client.get(_GET_ENDPOINT)
    assert response.status_code == 401


def test_get_assessments_returns_empty_list_when_none(client, analyst_headers):
    _cleanup_assessments()

    response = client.get(_GET_ENDPOINT, headers=analyst_headers)

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "success"
    data = body["data"]
    assert data["data"] == []
    assert data["total"] == 0


def test_get_assessments_returns_created_assessment(client, analyst_headers):
    _cleanup_assessments()
    client.post(_POST_ENDPOINT, json=_payload(), headers=analyst_headers)

    response = client.get(_GET_ENDPOINT, headers=analyst_headers)

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["total"] == 1
    assert len(data["data"]) == 1
    item = data["data"][0]
    assert item["conduta"] == "Dieta hipercalorica hipoproteica"
    assert item["ingestao"] == 70
    assert item["created_at"] is not None


def test_get_assessments_respects_limit_param(client, analyst_headers):
    _cleanup_assessments()
    for i in range(3):
        client.post(_POST_ENDPOINT, json=_payload(conduta=f"Conduta {i}"), headers=analyst_headers)

    response = client.get(f"{_GET_ENDPOINT}?limit=2", headers=analyst_headers)

    data = response.get_json()["data"]
    assert data["total"] == 3
    assert len(data["data"]) == 2


def test_get_assessments_returns_most_recent_first(client, analyst_headers):
    _cleanup_assessments()
    client.post(_POST_ENDPOINT, json=_payload(conduta="Primeira"), headers=analyst_headers)
    client.post(_POST_ENDPOINT, json=_payload(conduta="Segunda"), headers=analyst_headers)

    response = client.get(_GET_ENDPOINT, headers=analyst_headers)

    data = response.get_json()["data"]["data"]
    assert data[0]["conduta"] == "Segunda"
    assert data[1]["conduta"] == "Primeira"
