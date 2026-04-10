"""Integration tests for GET /nutritional/patients endpoint (US-BE-03).

Covers:
- HTTP 200 (success, including empty results)
- HTTP 401 (missing token / insufficient permission)
- Response payload structure and all required fields
- dtalta IS NULL filter (only active admissions)
- nome_setor obtained via JOIN with demo.setor
- protocolo derived from segmentosetor → segmento.tp_segmento
- haval hours calculated from nutricional_avaliacao.created_at
- d7 boolean when D7 active with dt_prevista <= NOW()+48h
- imc calculated from peso (kg) and altura (cm)
- Patient name absent (LGPD)
- campo1 null in this version
- Filters ?setor= and ?ala= working
"""

import pytest
from sqlalchemy import text

from security.role import Role
from tests.conftest import get_access, make_headers, session, session_commit

ENDPOINT = "/nutritional/patients"

# High IDs to avoid collision with seed data
_SETOR_UTI = 900
_SETOR_ENF = 901
_SEG_UTI = 900  # tp_segmento = 1 → UTI
_SEG_ENF = 901  # tp_segmento = 2 → Enfermaria
_HOSPITAL = 1
_ADM_ACTIVE_UTI = 900001
_ADM_ACTIVE_ENF = 900002
_ADM_DISCHARGED = 900003

# ── Response fields that every patient object MUST contain ──────────
REQUIRED_FIELDS = {
    "id",
    "leito",
    "ala",
    "fksetor",
    "nome_setor",
    "protocolo",
    "idade",
    "dias",
    "peso",
    "imc",
    "dieta",
    "npo",
    "alergia",
    "al_ok",
    "campo1",
    "glim_diag",
    "glim_fen",
    "glim_etiol",
    "inst",
    "conduta",
    "haval",
    "d7",
    "pri",
    "sev",
    "hist",
}


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture(scope="module", autouse=True)
def setup_nutritional_module():
    """Create nutritional tables and seed all test data (module-scoped)."""
    _ensure_schema()
    _cleanup()
    _seed()
    yield
    _cleanup()


@pytest.fixture()
def dispensing_headers(client):
    """Headers with DISPENSING_MANAGER role — has NO READ_PRESCRIPTION."""
    return make_headers(get_access(client, roles=[Role.DISPENSING_MANAGER.value]))


@pytest.fixture()
def analyst_headers(client):
    """Headers with PRESCRIPTION_ANALYST role — has READ_PRESCRIPTION."""
    return make_headers(get_access(client, roles=[Role.PRESCRIPTION_ANALYST.value]))


# ── Schema / seed helpers ───────────────────────────────────────────


def _ensure_schema():
    """Ensure all required tables and columns exist in the test DB."""
    # pessoa may lack fksetor / leito in the test dump
    session.execute(
        text("ALTER TABLE demo.pessoa ADD COLUMN IF NOT EXISTS fksetor BIGINT")
    )
    session.execute(
        text("ALTER TABLE demo.pessoa ADD COLUMN IF NOT EXISTS leito VARCHAR(16)")
    )

    ddl_statements = [
        """CREATE TABLE IF NOT EXISTS demo.nutricional_avaliacao (
            idnutricional_avaliacao BIGSERIAL PRIMARY KEY,
            nratendimento BIGINT NOT NULL,
            conduta TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            created_by BIGINT NOT NULL DEFAULT 1
        )""",
        """CREATE TABLE IF NOT EXISTS demo.nutricional_d7 (
            idnutricional_d7 BIGSERIAL PRIMARY KEY,
            nratendimento BIGINT NOT NULL,
            concluido BOOLEAN NOT NULL DEFAULT FALSE,
            dt_prevista TIMESTAMP NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            created_by BIGINT NOT NULL DEFAULT 1
        )""",
        """CREATE TABLE IF NOT EXISTS demo.nutricional_triagem (
            idnutricional_triagem BIGSERIAL PRIMARY KEY,
            nratendimento BIGINT NOT NULL,
            classificacao TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            created_by BIGINT NOT NULL DEFAULT 1
        )""",
        """CREATE TABLE IF NOT EXISTS demo.nutricional_glim (
            idnutricional_glim BIGSERIAL PRIMARY KEY,
            nratendimento BIGINT NOT NULL,
            diagnostico TEXT,
            fenotipos TEXT[],
            etiologicos TEXT[],
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            created_by BIGINT NOT NULL DEFAULT 1
        )""",
        """CREATE TABLE IF NOT EXISTS demo.nutricional_alerta (
            idnutricional_alerta BIGSERIAL PRIMARY KEY,
            nratendimento BIGINT NOT NULL,
            alerta TEXT NOT NULL,
            ativo BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            created_by BIGINT NOT NULL DEFAULT 1
        )""",
    ]

    for ddl in ddl_statements:
        session.execute(text(ddl))

    session_commit()


def _seed():
    """Insert self-contained test data (segments, departments, patients, nutritional)."""

    # ── Segments ──
    session.execute(
        text(
            "INSERT INTO demo.segmento (idsegmento, nome, status, tp_segmento, cpoe, cpoe_ambulatorio) "
            "VALUES (:id, :nome, 1, :tp, false, false) ON CONFLICT DO NOTHING"
        ),
        {"id": _SEG_UTI, "nome": "Seg UTI Teste Nutri", "tp": 1},
    )
    session.execute(
        text(
            "INSERT INTO demo.segmento (idsegmento, nome, status, tp_segmento, cpoe, cpoe_ambulatorio) "
            "VALUES (:id, :nome, 1, :tp, false, false) ON CONFLICT DO NOTHING"
        ),
        {"id": _SEG_ENF, "nome": "Seg Enf Teste Nutri", "tp": 2},
    )

    # ── Departments (setor) ──
    session.execute(
        text(
            "INSERT INTO demo.setor (fksetor, fkhospital, nome) "
            "VALUES (:id, :hosp, :nome) ON CONFLICT DO NOTHING"
        ),
        {"id": _SETOR_UTI, "hosp": _HOSPITAL, "nome": "UTI Adulto Teste"},
    )
    session.execute(
        text(
            "INSERT INTO demo.setor (fksetor, fkhospital, nome) "
            "VALUES (:id, :hosp, :nome) ON CONFLICT DO NOTHING"
        ),
        {"id": _SETOR_ENF, "hosp": _HOSPITAL, "nome": "Enfermaria Teste"},
    )

    # ── Segment ↔ Department links ──
    session.execute(
        text(
            "INSERT INTO demo.segmentosetor (idsegmento, fkhospital, fksetor) "
            "VALUES (:seg, :hosp, :setor) ON CONFLICT DO NOTHING"
        ),
        {"seg": _SEG_UTI, "hosp": _HOSPITAL, "setor": _SETOR_UTI},
    )
    session.execute(
        text(
            "INSERT INTO demo.segmentosetor (idsegmento, fkhospital, fksetor) "
            "VALUES (:seg, :hosp, :setor) ON CONFLICT DO NOTHING"
        ),
        {"seg": _SEG_ENF, "hosp": _HOSPITAL, "setor": _SETOR_ENF},
    )

    # ── Patients ──
    # Active UTI patient (no discharge date)
    session.execute(
        text(
            "INSERT INTO demo.pessoa "
            "(fkpessoa, fkhospital, nratendimento, dtinternacao, dtnascimento, "
            " sexo, peso, altura, fksetor, leito) "
            "VALUES (:pk, :hosp, :adm, NOW() - INTERVAL '14 days', '1959-03-15', "
            " 'M', 58.0, 183.0, :setor, 'UTI-03')"
        ),
        {
            "pk": _ADM_ACTIVE_UTI,
            "hosp": _HOSPITAL,
            "adm": _ADM_ACTIVE_UTI,
            "setor": _SETOR_UTI,
        },
    )
    # Active Enfermaria patient (no discharge date)
    session.execute(
        text(
            "INSERT INTO demo.pessoa "
            "(fkpessoa, fkhospital, nratendimento, dtinternacao, dtnascimento, "
            " sexo, peso, altura, fksetor, leito) "
            "VALUES (:pk, :hosp, :adm, NOW() - INTERVAL '5 days', '1990-08-22', "
            " 'F', 65.0, 160.0, :setor, 'ENF-12')"
        ),
        {
            "pk": _ADM_ACTIVE_ENF,
            "hosp": _HOSPITAL,
            "adm": _ADM_ACTIVE_ENF,
            "setor": _SETOR_ENF,
        },
    )
    # Discharged patient — must NOT appear in results
    session.execute(
        text(
            "INSERT INTO demo.pessoa "
            "(fkpessoa, fkhospital, nratendimento, dtinternacao, dtnascimento, "
            " sexo, peso, altura, fksetor, leito, dtalta) "
            "VALUES (:pk, :hosp, :adm, NOW() - INTERVAL '10 days', '1975-01-10', "
            " 'M', 80.0, 175.0, :setor, 'ENF-05', NOW())"
        ),
        {
            "pk": _ADM_DISCHARGED,
            "hosp": _HOSPITAL,
            "adm": _ADM_DISCHARGED,
            "setor": _SETOR_ENF,
        },
    )

    # ── Nutritional evaluation for the UTI patient ──
    session.execute(
        text(
            "INSERT INTO demo.nutricional_avaliacao "
            "(nratendimento, conduta, created_at, created_by) "
            "VALUES (:adm, 'Dieta hipercalorica', NOW() - INTERVAL '3 hours', 1)"
        ),
        {"adm": _ADM_ACTIVE_UTI},
    )

    # ── D7 active and expiring within 48h for the UTI patient ──
    session.execute(
        text(
            "INSERT INTO demo.nutricional_d7 "
            "(nratendimento, concluido, dt_prevista, created_at, created_by) "
            "VALUES (:adm, false, NOW() + INTERVAL '24 hours', NOW(), 1)"
        ),
        {"adm": _ADM_ACTIVE_UTI},
    )

    # ── Triage for UTI patient ──
    session.execute(
        text(
            "INSERT INTO demo.nutricional_triagem "
            "(nratendimento, classificacao, created_at, created_by) "
            "VALUES (:adm, 'al', NOW(), 1)"
        ),
        {"adm": _ADM_ACTIVE_UTI},
    )

    session_commit()


def _cleanup():
    """Remove all test-generated data (high-ID ranges)."""
    session.execute(
        text("DELETE FROM demo.nutricional_avaliacao WHERE nratendimento >= 900000")
    )
    session.execute(
        text("DELETE FROM demo.nutricional_d7 WHERE nratendimento >= 900000")
    )
    session.execute(
        text("DELETE FROM demo.nutricional_triagem WHERE nratendimento >= 900000")
    )
    session.execute(
        text("DELETE FROM demo.nutricional_glim WHERE nratendimento >= 900000")
    )
    session.execute(
        text("DELETE FROM demo.nutricional_alerta WHERE nratendimento >= 900000")
    )
    session.execute(text("DELETE FROM demo.pessoa WHERE nratendimento >= 900000"))
    session.execute(
        text("DELETE FROM demo.segmentosetor WHERE fksetor IN (:s1, :s2)"),
        {"s1": _SETOR_UTI, "s2": _SETOR_ENF},
    )
    session.execute(
        text("DELETE FROM demo.setor WHERE fksetor IN (:s1, :s2)"),
        {"s1": _SETOR_UTI, "s2": _SETOR_ENF},
    )
    session.execute(
        text("DELETE FROM demo.segmento WHERE idsegmento IN (:s1, :s2)"),
        {"s1": _SEG_UTI, "s2": _SEG_ENF},
    )
    session_commit()


# ── Helpers ─────────────────────────────────────────────────────────


def _find_patient(data, admission_number):
    """Find a patient dict in the response list by admission number."""
    for p in data:
        if p["id"] == admission_number:
            return p
    return None


# ═══════════════════════════════════════════════════════════════════
# HTTP STATUS TESTS
# ═══════════════════════════════════════════════════════════════════


def test_get_nutritional_patients_200(client, analyst_headers):
    """GET /nutritional/patients — 200 OK com role READ_PRESCRIPTION"""
    response = client.get(ENDPOINT, headers=analyst_headers)

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "success"
    assert isinstance(body["data"], list)


def test_get_nutritional_patients_401_no_token(client):
    """GET /nutritional/patients — 401 quando token ausente"""
    response = client.get(ENDPOINT)

    assert response.status_code == 401


def test_get_nutritional_patients_401_no_permission(client, dispensing_headers):
    """GET /nutritional/patients — 401 quando role não tem READ_PRESCRIPTION"""
    response = client.get(ENDPOINT, headers=dispensing_headers)

    assert response.status_code == 401


# ═══════════════════════════════════════════════════════════════════
# RESPONSE STRUCTURE TESTS
# ═══════════════════════════════════════════════════════════════════


def test_response_contains_all_required_fields(client, analyst_headers):
    """Cada objeto paciente deve conter TODOS os campos especificados na US"""
    response = client.get(ENDPOINT, headers=analyst_headers)
    data = response.get_json()["data"]

    # Must have at least our test patients
    assert len(data) >= 2

    for patient in data:
        missing = REQUIRED_FIELDS - set(patient.keys())
        assert missing == set(), f"Campos faltando: {missing}"


def test_patient_name_absent_lgpd(client, analyst_headers):
    """Nome do paciente NÃO deve estar na resposta (LGPD)"""
    response = client.get(ENDPOINT, headers=analyst_headers)
    data = response.get_json()["data"]

    forbidden_keys = {"nome", "name", "nome_paciente", "patient_name"}
    for patient in data:
        present = forbidden_keys & set(patient.keys())
        assert present == set(), f"Campo de nome presente na resposta: {present}"


def test_campo1_is_null(client, analyst_headers):
    """campo1 deve ser null nesta versão (populado em US-BE-07)"""
    response = client.get(ENDPOINT, headers=analyst_headers)
    data = response.get_json()["data"]

    for patient in data:
        assert patient["campo1"] is None


# ═══════════════════════════════════════════════════════════════════
# BUSINESS LOGIC TESTS
# ═══════════════════════════════════════════════════════════════════


def test_only_active_admissions(client, analyst_headers):
    """Retorna apenas admissões com dtalta IS NULL (sem pacientes com alta)"""
    response = client.get(ENDPOINT, headers=analyst_headers)
    data = response.get_json()["data"]

    ids = [p["id"] for p in data]
    assert _ADM_ACTIVE_UTI in ids, "Paciente ativo UTI deveria estar presente"
    assert _ADM_ACTIVE_ENF in ids, "Paciente ativo Enf deveria estar presente"
    assert _ADM_DISCHARGED not in ids, "Paciente com alta NÃO deveria estar presente"


def test_nome_setor_via_join(client, analyst_headers):
    """nome_setor deve ser obtido via JOIN com demo.setor"""
    response = client.get(ENDPOINT, headers=analyst_headers)
    data = response.get_json()["data"]

    uti = _find_patient(data, _ADM_ACTIVE_UTI)
    enf = _find_patient(data, _ADM_ACTIVE_ENF)

    assert uti is not None
    assert uti["nome_setor"] == "UTI Adulto Teste"
    assert enf is not None
    assert enf["nome_setor"] == "Enfermaria Teste"


def test_protocolo_derivation(client, analyst_headers):
    """Protocolo: MNUTRIC quando UTI (tp_segmento=1), NRS2002 caso contrário"""
    response = client.get(ENDPOINT, headers=analyst_headers)
    data = response.get_json()["data"]

    uti = _find_patient(data, _ADM_ACTIVE_UTI)
    enf = _find_patient(data, _ADM_ACTIVE_ENF)

    assert uti["protocolo"] == "MNUTRIC"
    assert uti["ala"] == "UTI"

    assert enf["protocolo"] == "NRS2002"
    assert enf["ala"] == "Enfermaria"


def test_imc_calculation(client, analyst_headers):
    """IMC = peso / (altura_cm / 100)² — paciente UTI: 58 / (1.83)² ≈ 17.3"""
    response = client.get(ENDPOINT, headers=analyst_headers)
    data = response.get_json()["data"]

    uti = _find_patient(data, _ADM_ACTIVE_UTI)
    assert uti["peso"] == 58.0
    # 58 / (183/100)^2 = 58 / 3.3489 ≈ 17.3
    assert uti["imc"] is not None
    assert 17.0 <= uti["imc"] <= 17.5

    enf = _find_patient(data, _ADM_ACTIVE_ENF)
    assert enf["peso"] == 65.0
    # 65 / (160/100)^2 = 65 / 2.56 ≈ 25.4
    assert enf["imc"] is not None
    assert 25.0 <= enf["imc"] <= 26.0


def test_haval_calculation(client, analyst_headers):
    """haval: horas desde a última avaliação — UTI tem avaliação (≈3h), Enf não tem (null)"""
    response = client.get(ENDPOINT, headers=analyst_headers)
    data = response.get_json()["data"]

    uti = _find_patient(data, _ADM_ACTIVE_UTI)
    assert uti["haval"] is not None
    # Evaluation was created ~3 hours ago
    assert 2.5 <= uti["haval"] <= 4.0

    enf = _find_patient(data, _ADM_ACTIVE_ENF)
    assert enf["haval"] is None, "Sem avaliação → haval deve ser null"


def test_d7_calculation(client, analyst_headers):
    """d7: true quando D7 ativo com dt_prevista <= NOW()+48h"""
    response = client.get(ENDPOINT, headers=analyst_headers)
    data = response.get_json()["data"]

    uti = _find_patient(data, _ADM_ACTIVE_UTI)
    assert uti["d7"] is True, "UTI tem D7 ativo vencendo em 24h"

    enf = _find_patient(data, _ADM_ACTIVE_ENF)
    assert enf["d7"] is False, "Enf não tem D7 → false"


def test_idade_and_dias(client, analyst_headers):
    """idade: anos completos; dias: dias de internação"""
    response = client.get(ENDPOINT, headers=analyst_headers)
    data = response.get_json()["data"]

    uti = _find_patient(data, _ADM_ACTIVE_UTI)
    # Born 1959-03-15, today 2026-04-10 → 67 years
    assert uti["idade"] == 67
    # Admitted 14 days ago
    assert uti["dias"] == 14

    enf = _find_patient(data, _ADM_ACTIVE_ENF)
    # Born 1990-08-22, today 2026-04-10 → 35 years
    assert enf["idade"] == 35
    # Admitted 5 days ago
    assert enf["dias"] == 5


def test_conduta_and_sev(client, analyst_headers):
    """conduta: última conduta; sev: classificação da triagem"""
    response = client.get(ENDPOINT, headers=analyst_headers)
    data = response.get_json()["data"]

    uti = _find_patient(data, _ADM_ACTIVE_UTI)
    assert uti["conduta"] == "Dieta hipercalorica"
    assert uti["sev"] == "al"

    enf = _find_patient(data, _ADM_ACTIVE_ENF)
    assert enf["conduta"] is None
    assert enf["sev"] == "bx"  # default Sprint 0


def test_default_null_fields(client, analyst_headers):
    """Campos não implementados nesta US devem retornar null/vazio"""
    response = client.get(ENDPOINT, headers=analyst_headers)
    data = response.get_json()["data"]

    for patient in data:
        assert patient["campo1"] is None
        assert patient["hist"] == []
        assert isinstance(patient["glim_fen"], list)
        assert isinstance(patient["glim_etiol"], list)
        assert isinstance(patient["inst"], list)


# ═══════════════════════════════════════════════════════════════════
# FILTER TESTS
# ═══════════════════════════════════════════════════════════════════


def test_filter_by_setor(client, analyst_headers):
    """Filtro ?setor= retorna apenas pacientes do setor informado"""
    response = client.get(
        f"{ENDPOINT}?setor={_SETOR_UTI}", headers=analyst_headers
    )
    data = response.get_json()["data"]

    assert response.status_code == 200
    assert len(data) >= 1
    for p in data:
        assert p["fksetor"] == _SETOR_UTI


def test_filter_by_setor_empty(client, analyst_headers):
    """Filtro ?setor= com setor inexistente retorna array vazio (200 OK)"""
    response = client.get(f"{ENDPOINT}?setor=999999", headers=analyst_headers)

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data == []


def test_filter_by_ala_uti(client, analyst_headers):
    """Filtro ?ala=UTI retorna apenas pacientes de setores UTI"""
    response = client.get(f"{ENDPOINT}?ala=UTI", headers=analyst_headers)
    data = response.get_json()["data"]

    assert response.status_code == 200
    assert len(data) >= 1
    for p in data:
        assert p["ala"] == "UTI"
        assert p["protocolo"] == "MNUTRIC"


def test_filter_by_ala_enfermaria(client, analyst_headers):
    """Filtro ?ala=Enfermaria retorna apenas pacientes de alas não-UTI"""
    response = client.get(f"{ENDPOINT}?ala=Enfermaria", headers=analyst_headers)
    data = response.get_json()["data"]

    assert response.status_code == 200
    assert len(data) >= 1
    for p in data:
        assert p["ala"] == "Enfermaria"
        assert p["protocolo"] == "NRS2002"


def test_filter_setor_and_ala_combined(client, analyst_headers):
    """Filtros ?setor= e ?ala= combinados funcionam corretamente"""
    response = client.get(
        f"{ENDPOINT}?setor={_SETOR_UTI}&ala=UTI", headers=analyst_headers
    )
    data = response.get_json()["data"]

    assert response.status_code == 200
    for p in data:
        assert p["fksetor"] == _SETOR_UTI
        assert p["ala"] == "UTI"

