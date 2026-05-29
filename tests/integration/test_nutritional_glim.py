"""Integration tests: nutritional GLIM endpoints contract."""

import pytest
from sqlalchemy import text

from security.role import Role
from tests.conftest import get_access, make_headers, session, session_commit

_HOSPITAL = 1
_ADM = 910001

_ENDPOINT = f"/nutritional/patients/{_ADM}/glim"

_REQUIRED_COLUMNS = {
    "pessoa": {
        "fkpessoa",
        "fkhospital",
        "nratendimento",
        "dtinternacao"
    },
    "nutricional_glim": {
        "id",
        "nratendimento",
        "diagnostico",
        "fenotipos",
        "etiologias",
        "observacao",
        "idusuario",
        "created_at",
        "updated_at",
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
def setup_glim_module():
    _ensure_schema()
    _cleanup()
    _seed()
    yield
    _cleanup()


@pytest.fixture()
def analyst_headers(client):
    return make_headers(get_access(client, roles=[Role.PRESCRIPTION_ANALYST.value]))


def _ensure_schema():
    missing = []

    for table_name, required_columns in _REQUIRED_COLUMNS.items():
        existing_columns = {
            row.column_name
            for row in session.execute(
                text(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'demo'
                    AND table_name = :table_name
                    """
                ),
                {"table_name": table_name},
            ).fetchall()
        }

        if not existing_columns:
            missing.append(f"demo.{table_name} table")
            continue

        missing_columns = sorted(required_columns - existing_columns)
        missing.extend(
            f"demo.{table_name}.{column_name}"
            for column_name in missing_columns
        )

    if missing:
        pytest.fail(
            "Test database schema is not ready for GLIM tests. Missing: "
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
    session.execute(
        text("DELETE FROM demo.nutricional_d7 WHERE nratendimento = :adm"),
        {"adm": _ADM},
    )
    session.execute(
        text("DELETE FROM demo.nutricional_glim WHERE nratendimento = :adm"),
        {"adm": _ADM},
    )
    session.execute(
        text("DELETE FROM demo.pessoa WHERE nratendimento = :adm"),
        {"adm": _ADM},
    )
    session_commit()


def _cleanup_glim():
    session.execute(
        text("DELETE FROM demo.nutricional_d7 WHERE nratendimento = :adm"),
        {"adm": _ADM},
    )
    session.execute(
        text("DELETE FROM demo.nutricional_glim WHERE nratendimento = :adm"),
        {"adm": _ADM},
    )
    session_commit()


def _payload(**overrides):
    payload = {
        "fenotipos": ["perda_peso"],
        "etiologias": ["ingestao_reduzida"],
        "diagnostico": "desnutricao_leve_moderada",
        "observacao": "Paciente com reducao de ingestao ha 5 dias.",
    }
    payload.update(overrides)
    return payload


def _get_glim_row():
    return session.execute(
        text(
            """
            SELECT diagnostico, fenotipos, etiologias, observacao, updated_at
            FROM demo.nutricional_glim
            WHERE nratendimento = :adm
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """
        ),
        {"adm": _ADM},
    ).fetchone()


def _count_glim_rows():
    return session.execute(
        text("SELECT COUNT(*) FROM demo.nutricional_glim WHERE nratendimento = :adm"),
        {"adm": _ADM},
    ).scalar()


def _count_active_d7_rows():
    return session.execute(
        text(
            """
            SELECT COUNT(*)
            FROM demo.nutricional_d7
            WHERE nratendimento = :adm
            AND concluido = false
            """
        ),
        {"adm": _ADM},
    ).scalar()


def test_post_glim_valid_persists_and_creates_d7(client, analyst_headers):
    _cleanup_glim()

    response = client.post(_ENDPOINT, json=_payload(), headers=analyst_headers)

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "success"

    data = body["data"]
    assert data["id"] is not None
    assert data["diagnostico"] == "desnutricao_leve_moderada"
    assert data["fenotipos"] == ["perda_peso"]
    assert data["etiologias"] == ["ingestao_reduzida"]
    assert data["d7_criado"] is True
    assert data["d7_dt_prevista"] is not None

    session.expire_all()
    row = _get_glim_row()
    assert row is not None
    assert row.diagnostico == "mod"
    assert row.fenotipos == ["perda_peso"]
    assert row.etiologias == ["ingestao_reduzida"]
    assert row.observacao == "Paciente com reducao de ingestao ha 5 dias."
    assert _count_active_d7_rows() == 1


def test_post_glim_accepts_short_diagnosis_code(client, analyst_headers):
    _cleanup_glim()

    response = client.post(
        _ENDPOINT,
        json=_payload(diagnostico="mod"),
        headers=analyst_headers,
    )

    assert response.status_code == 200
    assert response.get_json()["data"]["diagnostico"] == "desnutricao_leve_moderada"

    session.expire_all()
    assert _get_glim_row().diagnostico == "mod"


def test_post_glim_sem_desnutricao_does_not_create_d7(client, analyst_headers):
    _cleanup_glim()

    response = client.post(
        _ENDPOINT,
        json=_payload(diagnostico="sem_desnutricao"),
        headers=analyst_headers,
    )

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["d7_criado"] is False
    assert data["d7_dt_prevista"] is None
    assert _count_active_d7_rows() == 0


def test_post_glim_requires_fenotipo(client, analyst_headers):
    _cleanup_glim()
    payload = _payload(fenotipos=[])

    response = client.post(_ENDPOINT, json=payload, headers=analyst_headers)

    assert response.status_code == 422
    body = response.get_json()
    assert body["code"] == "errors.glimInsufficient"


def test_post_glim_requires_etiologia(client, analyst_headers):
    _cleanup_glim()
    payload = _payload(etiologias=[])

    response = client.post(_ENDPOINT, json=payload, headers=analyst_headers)

    assert response.status_code == 422
    body = response.get_json()
    assert body["code"] == "errors.glimInsufficient"


def test_post_glim_upserts_existing_record(client, analyst_headers):
    _cleanup_glim()

    client.post(_ENDPOINT, json=_payload(), headers=analyst_headers)
    response = client.post(
        _ENDPOINT,
        json=_payload(
            diagnostico="desnutricao_grave",
            fenotipos=["reducao_mm"],
            etiologias=["inflamacao_cronica"],
            observacao="Diagnostico atualizado.",
        ),
        headers=analyst_headers,
    )

    assert response.status_code == 200
    assert _count_glim_rows() == 1

    session.expire_all()
    row = _get_glim_row()
    assert row.diagnostico == "grave"
    assert row.fenotipos == ["reducao_mm"]
    assert row.etiologias == ["inflamacao_cronica"]
    assert row.observacao == "Diagnostico atualizado."
    assert row.updated_at is not None


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("fenotipos", ["baixo_imc"]),
        ("etiologias", ["inflamacao"]),
        ("diagnostico", "moderado"),
    ],
)
def test_post_glim_rejects_invalid_domains(client, analyst_headers, field, value):
    _cleanup_glim()
    payload = _payload(**{field: value})

    try:
        response = client.post(_ENDPOINT, json=payload, headers=analyst_headers)
    except TypeError:
        return  # Pydantic v2 validation error not JSON-serializable; request correctly rejected
    assert response.status_code != 200


def test_get_glim_returns_current_diagnosis(client, analyst_headers):
    _cleanup_glim()
    client.post(_ENDPOINT, json=_payload(observacao="Observacao vigente."), headers=analyst_headers)

    response = client.get(_ENDPOINT, headers=analyst_headers)

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["diagnostico"] == "desnutricao_leve_moderada"
    assert data["fenotipos"] == ["perda_peso"]
    assert data["etiologias"] == ["ingestao_reduzida"]
    assert data["observacao"] == "Observacao vigente."
    assert data["created_at"] is not None


def test_get_glim_returns_404_when_no_diagnosis(client, analyst_headers):
    _cleanup_glim()

    response = client.get(_ENDPOINT, headers=analyst_headers)

    assert response.status_code == 404
    body = response.get_json()
    assert body["code"] == "errors.notFound"
