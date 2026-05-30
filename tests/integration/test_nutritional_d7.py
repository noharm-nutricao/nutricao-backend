"""Integration tests: nutritional D7 endpoints contract."""

import pytest
from sqlalchemy import text

from security.role import Role
from tests.conftest import get_access, make_headers, session, session_commit

_HOSPITAL = 1
_ADM = 900001
_ADM_NOT_FOUND = 999998

_POST_ENDPOINT = f"/nutritional/patients/{_ADM}/d7"
_GET_ENDPOINT = f"/nutritional/patients/{_ADM}/d7"


def _put_endpoint(id):
    return f"/nutritional/patients/{_ADM}/d7/{id}/close"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module", autouse=True)
def setup_d7_module():
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
    """Ensure nutricional_d7 table has the updated_at column."""
    session.execute(
        text(
            "ALTER TABLE demo.nutricional_d7 ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ"
        )
    )
    session_commit()


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
    session.execute(
        text("DELETE FROM demo.nutricional_d7 WHERE nratendimento = :adm"),
        {"adm": _ADM},
    )
    session.execute(
        text("DELETE FROM demo.pessoa WHERE nratendimento = :adm"),
        {"adm": _ADM},
    )
    session_commit()


def _get_d7_row(nratendimento=_ADM):
    return session.execute(
        text(
            "SELECT id, dt_prevista, concluido, updated_at "
            "FROM demo.nutricional_d7 WHERE nratendimento = :adm "
            "ORDER BY created_at DESC LIMIT 1"
        ),
        {"adm": nratendimento},
    ).fetchone()


# ---------------------------------------------------------------------------
# POST /nutritional/patients/:nratendimento/d7
# ---------------------------------------------------------------------------


def test_post_d7_requires_authorization(client):
    """POST /d7 - sem token deve retornar 401"""
    response = client.post(_POST_ENDPOINT, content_type="application/json")
    assert response.status_code == 401


def test_post_d7_requires_write_nutritional_permission(client, viewer_headers):
    """POST /d7 - role sem permissão deve retornar 401"""
    response = client.post(_POST_ENDPOINT, headers=viewer_headers)
    assert response.status_code == 401


def test_post_d7_creates_d7_successfully(client, analyst_headers):
    """POST /d7 - cria D7 e retorna 200 com estrutura correta"""
    _cleanup_d7()

    response = client.post(_POST_ENDPOINT, headers=analyst_headers)

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "success"
    data = body["data"]
    assert "id" in data
    assert "dt_prevista" in data
    assert "status" in data
    assert data["status"] == "pendente"


def test_post_d7_persists_in_db(client, analyst_headers):
    """POST /d7 - grava registro na tabela nutricional_d7"""
    _cleanup_d7()

    client.post(_POST_ENDPOINT, headers=analyst_headers)

    session.expire_all()
    row = _get_d7_row()
    assert row is not None
    assert row.concluido is False


def test_post_d7_dt_prevista_is_7_days_ahead(client, analyst_headers):
    """POST /d7 - dt_prevista deve ser aproximadamente now + 7 dias"""
    _cleanup_d7()

    response = client.post(_POST_ENDPOINT, headers=analyst_headers)

    body = response.get_json()
    dt_prevista_str = body["data"]["dt_prevista"]
    assert dt_prevista_str is not None

    session.expire_all()
    row = _get_d7_row()
    assert row is not None

    from datetime import datetime, timedelta
    now = datetime.now()
    expected_min = now + timedelta(days=6, hours=23)
    expected_max = now + timedelta(days=7, hours=1)

    dt = row.dt_prevista
    if dt.tzinfo is not None:
        dt = dt.astimezone().replace(tzinfo=None)

    assert expected_min <= dt <= expected_max


def test_post_d7_upserts_existing_active_d7(client, analyst_headers):
    """POST /d7 - segundo POST atualiza dt_prevista sem criar novo registro"""
    _cleanup_d7()

    client.post(_POST_ENDPOINT, headers=analyst_headers)
    session.expire_all()
    row_first = _get_d7_row()
    first_id = row_first.id

    client.post(_POST_ENDPOINT, headers=analyst_headers)
    session.expire_all()
    row_second = _get_d7_row()

    assert row_second.id == first_id

    count = session.execute(
        text("SELECT COUNT(*) FROM demo.nutricional_d7 WHERE nratendimento = :adm AND concluido = false"),
        {"adm": _ADM},
    ).scalar()
    assert count == 1


def test_post_d7_status_is_pendente(client, analyst_headers):
    """POST /d7 - status deve ser 'pendente' para D7 recém-criado"""
    _cleanup_d7()

    response = client.post(_POST_ENDPOINT, headers=analyst_headers)

    assert response.get_json()["data"]["status"] == "pendente"


# ---------------------------------------------------------------------------
# GET /nutritional/patients/:nratendimento/d7
# ---------------------------------------------------------------------------


def test_get_d7_requires_authorization(client):
    """GET /d7 - sem token deve retornar 401"""
    response = client.get(_GET_ENDPOINT)
    assert response.status_code == 401


def test_get_d7_returns_none_when_no_active_d7(client, analyst_headers):
    """GET /d7 - retorna null quando não há D7 ativo"""
    _cleanup_d7()

    response = client.get(_GET_ENDPOINT, headers=analyst_headers)

    assert response.status_code == 200
    assert response.get_json()["data"] is None


def test_get_d7_returns_active_d7(client, analyst_headers):
    """GET /d7 - retorna D7 ativo com campos corretos"""
    _cleanup_d7()
    client.post(_POST_ENDPOINT, headers=analyst_headers)

    response = client.get(_GET_ENDPOINT, headers=analyst_headers)

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data is not None
    assert "id" in data
    assert "dt_prevista" in data
    assert "concluido" in data
    assert "status" in data
    assert data["concluido"] is False


def test_get_d7_status_is_valid_value(client, analyst_headers):
    """GET /d7 - status deve ser um valor válido"""
    _cleanup_d7()
    client.post(_POST_ENDPOINT, headers=analyst_headers)

    response = client.get(_GET_ENDPOINT, headers=analyst_headers)

    status_value = response.get_json()["data"]["status"]
    assert status_value in {"pendente", "vencendo", "vencido", "concluido"}


def test_get_d7_does_not_return_concluded_d7(client, analyst_headers):
    """GET /d7 - D7 closed não deve aparecer como ativo"""
    _cleanup_d7()
    post_response = client.post(_POST_ENDPOINT, headers=analyst_headers)
    d7_id = post_response.get_json()["data"]["id"]

    client.put(_put_endpoint(d7_id), headers=analyst_headers)

    response = client.get(_GET_ENDPOINT, headers=analyst_headers)

    assert response.get_json()["data"] is None


# ---------------------------------------------------------------------------
# PUT /nutritional/patients/:nratendimento/d7/:id/close
# ---------------------------------------------------------------------------


def test_put_close_requires_authorization(client):
    """PUT /d7/:id/close - sem token deve retornar 401"""
    response = client.put(_put_endpoint(1))
    assert response.status_code == 401


def test_put_close_returns_404_for_nonexistent_d7(client, analyst_headers):
    """PUT /d7/:id/close - id inexistente deve retornar 404"""
    response = client.put(_put_endpoint(999999), headers=analyst_headers)
    assert response.status_code == 404


def test_put_close_marks_d7_as_concluded(client, analyst_headers):
    """PUT /d7/:id/close - deve setar concluido=true e retornar 200"""
    _cleanup_d7()
    post_response = client.post(_POST_ENDPOINT, headers=analyst_headers)
    d7_id = post_response.get_json()["data"]["id"]

    response = client.put(_put_endpoint(d7_id), headers=analyst_headers)

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["concluido"] is True
    assert data["status"] == "concluido"
    assert data["updated_at"] is not None


def test_put_close_persists_in_db(client, analyst_headers):
    """PUT /d7/:id/close - atualiza concluido e updated_at no banco"""
    _cleanup_d7()
    post_response = client.post(_POST_ENDPOINT, headers=analyst_headers)
    d7_id = post_response.get_json()["data"]["id"]

    client.put(_put_endpoint(d7_id), headers=analyst_headers)

    session.expire_all()
    row = _get_d7_row()
    assert row.concluido is True
    assert row.updated_at is not None


def test_put_close_response_structure(client, analyst_headers):
    """PUT /d7/:id/close - resposta deve conter id, concluido, status e updated_at"""
    _cleanup_d7()
    post_response = client.post(_POST_ENDPOINT, headers=analyst_headers)
    d7_id = post_response.get_json()["data"]["id"]

    response = client.put(_put_endpoint(d7_id), headers=analyst_headers)

    data = response.get_json()["data"]
    assert "id" in data
    assert "concluido" in data
    assert "status" in data
    assert "updated_at" in data


# ---------------------------------------------------------------------------
# Full flow: create → get → close
# ---------------------------------------------------------------------------


def test_full_d7_lifecycle(client, analyst_headers):
    """Fluxo completo: POST cria, GET retorna ativo, PUT close, GET retorna null"""
    _cleanup_d7()

    # POST
    post_resp = client.post(_POST_ENDPOINT, headers=analyst_headers)
    assert post_resp.status_code == 200
    d7_id = post_resp.get_json()["data"]["id"]
    assert post_resp.get_json()["data"]["status"] == "pendente"

    # GET → ativo
    get_resp = client.get(_GET_ENDPOINT, headers=analyst_headers)
    assert get_resp.status_code == 200
    assert get_resp.get_json()["data"]["id"] == d7_id

    # PUT close
    put_resp = client.put(_put_endpoint(d7_id), headers=analyst_headers)
    assert put_resp.status_code == 200
    assert put_resp.get_json()["data"]["concluido"] is True

    # GET → null (closed não é ativo)
    get_after = client.get(_GET_ENDPOINT, headers=analyst_headers)
    assert get_after.status_code == 200
    assert get_after.get_json()["data"] is None


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_post_d7_with_motivo_body_succeeds(client, analyst_headers):
    """POST /d7 com body { motivo: ... } deve retornar 200 normalmente"""
    _cleanup_d7()

    response = client.post(
        _POST_ENDPOINT,
        json={"motivo": "diagnostico GLIM confirmado"},
        headers=analyst_headers,
    )

    assert response.status_code == 200
    assert response.get_json()["status"] == "success"


def test_post_d7_after_close_creates_new_d7(client, analyst_headers):
    """POST /d7 depois de close deve criar novo D7 com id diferente"""
    _cleanup_d7()

    post1 = client.post(_POST_ENDPOINT, headers=analyst_headers)
    d7_id_first = post1.get_json()["data"]["id"]

    client.put(_put_endpoint(d7_id_first), headers=analyst_headers)

    post2 = client.post(_POST_ENDPOINT, headers=analyst_headers)
    assert post2.status_code == 200
    d7_id_second = post2.get_json()["data"]["id"]

    assert d7_id_second != d7_id_first

    count = session.execute(
        text("SELECT COUNT(*) FROM demo.nutricional_d7 WHERE nratendimento = :adm"),
        {"adm": _ADM},
    ).scalar()
    assert count == 2


def test_put_close_wrong_nratendimento_returns_404(client, analyst_headers):
    """PUT /d7/:id/close com nratendimento errado deve retornar 404"""
    _cleanup_d7()
    post_response = client.post(_POST_ENDPOINT, headers=analyst_headers)
    d7_id = post_response.get_json()["data"]["id"]

    wrong_url = f"/nutritional/patients/{_ADM_NOT_FOUND}/d7/{d7_id}/close"
    response = client.put(wrong_url, headers=analyst_headers)

    assert response.status_code == 404


def test_post_d7_upsert_sets_updated_at(client, analyst_headers):
    """POST /d7 em upsert (segundo POST) deve setar updated_at no registro"""
    _cleanup_d7()

    client.post(_POST_ENDPOINT, headers=analyst_headers)
    session.expire_all()
    row_first = _get_d7_row()
    assert row_first.updated_at is None

    client.post(_POST_ENDPOINT, headers=analyst_headers)
    session.expire_all()
    row_second = _get_d7_row()

    assert row_second.updated_at is not None


def test_get_d7_status_vencendo_via_db(client, analyst_headers):
    """GET /d7 - status vencendo quando dt_prevista está entre now e now+48h"""
    _cleanup_d7()
    session.execute(
        text(
            "INSERT INTO demo.nutricional_d7 "
            "(nratendimento, dt_prevista, concluido, created_at) "
            "VALUES (:adm, NOW() + INTERVAL '24 hours', false, NOW())"
        ),
        {"adm": _ADM},
    )
    session_commit()

    response = client.get(_GET_ENDPOINT, headers=analyst_headers)

    assert response.status_code == 200
    assert response.get_json()["data"]["status"] == "vencendo"


def test_get_d7_status_vencido_via_db(client, analyst_headers):
    """GET /d7 - status vencido quando dt_prevista já passou"""
    _cleanup_d7()
    session.execute(
        text(
            "INSERT INTO demo.nutricional_d7 "
            "(nratendimento, dt_prevista, concluido, created_at) "
            "VALUES (:adm, NOW() - INTERVAL '1 hour', false, NOW())"
        ),
        {"adm": _ADM},
    )
    session_commit()

    response = client.get(_GET_ENDPOINT, headers=analyst_headers)

    assert response.status_code == 200
    assert response.get_json()["data"]["status"] == "vencido"

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _cleanup_d7():
    session.execute(
        text("DELETE FROM demo.nutricional_d7 WHERE nratendimento = :adm"),
        {"adm": _ADM},
    )
    session_commit()
