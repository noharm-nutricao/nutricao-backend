import pytest
from sqlalchemy import text

from security.role import Role
from tests.conftest import get_access, make_headers, session, session_commit

_HOSPITAL = 1
_ADM = 910001
_ALERT_ACTIVE = 910101
_ALERT_INACTIVE = 910102
_ALERT_RECOGNIZED = 910103


def _post_endpoint(alert_id):
    return f"/nutritional/patients/{_ADM}/alerts/{alert_id}/acknowledge"


@pytest.fixture(scope="module", autouse=True)
def setup_module():
    _cleanup()
    _seed_person()
    yield
    _cleanup()


@pytest.fixture()
def analyst_headers(client):
    return make_headers(get_access(client, roles=[Role.PRESCRIPTION_ANALYST.value]))


@pytest.fixture()
def viewer_headers(client):
    return make_headers(get_access(client, roles=[Role.VIEWER.value]))


def test_acknowledge_requires_authorization(client):
    response = client.post(_post_endpoint(_ALERT_ACTIVE))
    assert response.status_code == 401


def test_acknowledge_requires_permission(client, viewer_headers):
    _cleanup_alerts()
    _insert_alert(alert_id=_ALERT_ACTIVE, ativo=True, reconhecido=False)
    response = client.post(_post_endpoint(_ALERT_ACTIVE), headers=viewer_headers)
    assert response.status_code == 401


def test_acknowledge_returns_404_when_missing(client, analyst_headers):
    _cleanup_alerts()
    response = client.post(_post_endpoint(_ALERT_ACTIVE), headers=analyst_headers)
    assert response.status_code == 404


def test_acknowledge_returns_404_when_inactive(client, analyst_headers):
    _cleanup_alerts()
    _insert_alert(alert_id=_ALERT_INACTIVE, ativo=False, reconhecido=False)
    response = client.post(_post_endpoint(_ALERT_INACTIVE), headers=analyst_headers)
    assert response.status_code == 404


def test_acknowledge_returns_409_when_already_recognized(client, analyst_headers):
    _cleanup_alerts()
    _insert_alert(alert_id=_ALERT_RECOGNIZED, ativo=True, reconhecido=True)
    response = client.post(_post_endpoint(_ALERT_RECOGNIZED), headers=analyst_headers)
    assert response.status_code == 409


def test_acknowledge_success_persists(client, analyst_headers):
    _cleanup_alerts()
    _insert_alert(alert_id=_ALERT_ACTIVE, ativo=True, reconhecido=False)
    response = client.post(_post_endpoint(_ALERT_ACTIVE), headers=analyst_headers)
    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "success"
    data = body["data"]
    assert data["id"] == _ALERT_ACTIVE
    assert data["reconhecido"] is True
    assert data["reconhecido_at"] is not None

    session.expire_all()
    row = _get_alert(_ALERT_ACTIVE)
    assert row is not None
    assert row.reconhecido is True
    assert row.reconhecido_por == _get_user_id()
    assert row.reconhecido_at is not None


def _seed_person():
    session.execute(
        text(
            "INSERT INTO demo.pessoa "
            "(fkpessoa, fkhospital, nratendimento, dtinternacao) "
            "VALUES (:pk, :hosp, :adm, NOW() - INTERVAL '2 days') "
            "ON CONFLICT DO NOTHING"
        ),
        {"pk": _ADM, "hosp": _HOSPITAL, "adm": _ADM},
    )
    session_commit()


def _insert_alert(alert_id, ativo, reconhecido):
    session.execute(
        text(
            "INSERT INTO demo.nutricional_alerta "
            "(id, nratendimento, tipo, descricao, severidade, ativo, reconhecido, reconhecido_por, reconhecido_at, created_at) "
            "VALUES (:id, :adm, :tipo, :descricao, :severidade, :ativo, :reconhecido, :reconhecido_por, "
            "CASE WHEN :reconhecido THEN NOW() ELSE NULL END, NOW())"
        ),
        {
            "id": alert_id,
            "adm": _ADM,
            "tipo": "lab",
            "descricao": "NPO",
            "severidade": "alta",
            "ativo": ativo,
            "reconhecido": reconhecido,
            "reconhecido_por": _get_user_id() if reconhecido else None,
        },
    )
    session_commit()


def _get_alert(alert_id):
    return session.execute(
        text(
            "SELECT reconhecido, reconhecido_por, reconhecido_at "
            "FROM demo.nutricional_alerta WHERE id = :id"
        ),
        {"id": alert_id},
    ).fetchone()


def _get_user_id(email="demo"):
    return session.execute(
        text("SELECT idusuario FROM demo.usuario WHERE email = :email"),
        {"email": email},
    ).scalar()


def _cleanup_alerts():
    session.execute(
        text("DELETE FROM demo.nutricional_alerta WHERE nratendimento = :adm"),
        {"adm": _ADM},
    )
    session_commit()


def _cleanup():
    _cleanup_alerts()
    session.execute(
        text("DELETE FROM demo.pessoa WHERE nratendimento = :adm"),
        {"adm": _ADM},
    )
    session_commit()

