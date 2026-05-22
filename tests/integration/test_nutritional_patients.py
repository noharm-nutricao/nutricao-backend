import pytest
from datetime import date
from sqlalchemy import text

from security.role import Role
from tests.conftest import get_access, make_headers, session, session_commit

ENDPOINT = "/nutritional/patients"

_SETOR_UTI = 900
_SETOR_ENF = 901
_SEG_UTI = 900
_SEG_ENF = 901
_HOSPITAL = 1
_ADM_ACTIVE_UTI = 900001
_ADM_ACTIVE_ENF = 900002
_ADM_DISCHARGED = 900003
_ADM_NO_WEIGHT = 900004

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


@pytest.fixture(scope="module", autouse=True)
def setup_nutritional_module():
    _ensure_schema()
    _cleanup()
    _seed()
    yield
    _cleanup()


@pytest.fixture()
def dispensing_headers(client):
    return make_headers(get_access(client, roles=[Role.DISPENSING_MANAGER.value]))


@pytest.fixture()
def analyst_headers(client):
    return make_headers(get_access(client, roles=[Role.PRESCRIPTION_ANALYST.value]))


def _ensure_schema():
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
            frequencia VARCHAR(32),
            ingestao INTEGER,
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
            id BIGSERIAL PRIMARY KEY,
            nratendimento BIGINT NOT NULL,
            protocolo VARCHAR(32) NOT NULL DEFAULT 'NRS2002',
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

    # Ensure columns added after initial DDL exist (idempotent)
    session.execute(text(
        "ALTER TABLE demo.nutricional_avaliacao ADD COLUMN IF NOT EXISTS frequencia VARCHAR(32)"
    ))
    session.execute(text(
        "ALTER TABLE demo.nutricional_avaliacao ADD COLUMN IF NOT EXISTS ingestao INTEGER"
    ))

    # nutricional_triagem: add columns required by NutritionalScreening model
    for col in [
        "ALTER TABLE demo.nutricional_triagem ADD COLUMN IF NOT EXISTS protocolo VARCHAR(32) NOT NULL DEFAULT 'NRS2002'",
        "ALTER TABLE demo.nutricional_triagem ADD COLUMN IF NOT EXISTS nrs_nut INTEGER",
        "ALTER TABLE demo.nutricional_triagem ADD COLUMN IF NOT EXISTS nrs_doenca INTEGER",
        "ALTER TABLE demo.nutricional_triagem ADD COLUMN IF NOT EXISTS nrs_idade INTEGER",
        "ALTER TABLE demo.nutricional_triagem ADD COLUMN IF NOT EXISTS nrs_total INTEGER",
        "ALTER TABLE demo.nutricional_triagem ADD COLUMN IF NOT EXISTS nrs_completo BOOLEAN NOT NULL DEFAULT FALSE",
        "ALTER TABLE demo.nutricional_triagem ADD COLUMN IF NOT EXISTS nrs_ref_at TIMESTAMP",
        "ALTER TABLE demo.nutricional_triagem ADD COLUMN IF NOT EXISTS mn_idade INTEGER",
        "ALTER TABLE demo.nutricional_triagem ADD COLUMN IF NOT EXISTS mn_apache INTEGER",
        "ALTER TABLE demo.nutricional_triagem ADD COLUMN IF NOT EXISTS mn_sofa INTEGER",
        "ALTER TABLE demo.nutricional_triagem ADD COLUMN IF NOT EXISTS mn_comor INTEGER",
        "ALTER TABLE demo.nutricional_triagem ADD COLUMN IF NOT EXISTS mn_dias INTEGER",
        "ALTER TABLE demo.nutricional_triagem ADD COLUMN IF NOT EXISTS mn_total INTEGER",
        "ALTER TABLE demo.nutricional_triagem ADD COLUMN IF NOT EXISTS mn_apache_manual BOOLEAN",
        "ALTER TABLE demo.nutricional_triagem ADD COLUMN IF NOT EXISTS mn_sofa_manual BOOLEAN",
        "ALTER TABLE demo.nutricional_triagem ADD COLUMN IF NOT EXISTS calculado_at TIMESTAMP",
        "ALTER TABLE demo.nutricional_triagem ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP",
    ]:
        session.execute(text(col))

    session_commit()


def _seed():
    session.execute(
        text(
            "INSERT INTO demo.segmento (idsegmento, nome, status, tp_segmento, cpoe, cpoe_ambulatorio) "
            "VALUES (:id, :nome, 1, :tp, false, false) ON CONFLICT DO NOTHING"
        ),
        {"id": _SEG_UTI, "nome": "Seg UTI Teste Nutri", "tp": 3},
    )
    session.execute(
        text(
            "INSERT INTO demo.segmento (idsegmento, nome, status, tp_segmento, cpoe, cpoe_ambulatorio) "
            "VALUES (:id, :nome, 1, :tp, false, false) ON CONFLICT DO NOTHING"
        ),
        {"id": _SEG_ENF, "nome": "Seg Enf Teste Nutri", "tp": 2},
    )

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
    session.execute(
        text(
            "INSERT INTO demo.pessoa "
            "(fkpessoa, fkhospital, nratendimento, dtinternacao, dtnascimento, "
            " sexo, peso, altura, fksetor, leito) "
            "VALUES (:pk, :hosp, :adm, NOW() - INTERVAL '3 days', '2000-01-15', "
            " 'M', NULL, NULL, :setor, 'ENF-20')"
        ),
        {
            "pk": _ADM_NO_WEIGHT,
            "hosp": _HOSPITAL,
            "adm": _ADM_NO_WEIGHT,
            "setor": _SETOR_ENF,
        },
    )
    session.execute(
        text(
            "INSERT INTO demo.nutricional_avaliacao "
            "(nratendimento, conduta, created_at, created_by) "
            "VALUES (:adm, 'Dieta hipercalorica', NOW() - INTERVAL '3 hours', 1)"
        ),
        {"adm": _ADM_ACTIVE_UTI},
    )
    session.execute(
        text(
            "INSERT INTO demo.nutricional_d7 "
            "(nratendimento, concluido, dt_prevista, created_at, created_by) "
            "VALUES (:adm, false, NOW() + INTERVAL '24 hours', NOW(), 1)"
        ),
        {"adm": _ADM_ACTIVE_UTI},
    )
    session.execute(
        text(
            "INSERT INTO demo.nutricional_triagem "
            "(nratendimento, classificacao, created_at, created_by) "
            "VALUES (:adm, 'al', NOW(), 1)"
        ),
        {"adm": _ADM_ACTIVE_UTI},
    )
    session.execute(
        text(
            "INSERT INTO demo.nutricional_glim "
            "(nratendimento, diagnostico, fenotipos, etiologicos, created_at, created_by) "
            "VALUES (:adm, 'mod', ARRAY['perda_peso', 'baixo_imc'], ARRAY['inflamacao'], NOW(), 1)"
        ),
        {"adm": _ADM_ACTIVE_UTI},
    )

    session_commit()


def _cleanup():
    _test_adms = [_ADM_ACTIVE_UTI, _ADM_ACTIVE_ENF, _ADM_DISCHARGED, _ADM_NO_WEIGHT]
    for adm in _test_adms:
        session.execute(
            text("DELETE FROM demo.nutricional_avaliacao WHERE nratendimento = :adm"),
            {"adm": adm},
        )
        session.execute(
            text("DELETE FROM demo.nutricional_d7 WHERE nratendimento = :adm"),
            {"adm": adm},
        )
        session.execute(
            text("DELETE FROM demo.nutricional_triagem WHERE nratendimento = :adm"),
            {"adm": adm},
        )
        session.execute(
            text("DELETE FROM demo.nutricional_glim WHERE nratendimento = :adm"),
            {"adm": adm},
        )
        session.execute(
            text("DELETE FROM demo.nutricional_alerta WHERE nratendimento = :adm"),
            {"adm": adm},
        )
        session.execute(
            text("DELETE FROM demo.pessoa WHERE nratendimento = :adm"),
            {"adm": adm},
        )
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


def _find_patient(data, admission_number):
    for p in data:
        if p["id"] == admission_number:
            return p
    return None


def test_get_nutritional_patients_200(client, analyst_headers):
    response = client.get(ENDPOINT, headers=analyst_headers)

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "success"
    assert isinstance(body["data"], list)


def test_get_nutritional_patients_401_no_token(client):
    response = client.get(ENDPOINT)

    assert response.status_code == 401


def test_get_nutritional_patients_401_no_permission(client, dispensing_headers):
    response = client.get(ENDPOINT, headers=dispensing_headers)

    assert response.status_code == 401


def test_response_contains_all_required_fields(client, analyst_headers):
    response = client.get(ENDPOINT, headers=analyst_headers)
    data = response.get_json()["data"]

    assert len(data) >= 2

    for patient in data:
        missing = REQUIRED_FIELDS - set(patient.keys())
        assert missing == set(), f"Campos faltando: {missing}"


def test_patient_name_absent_lgpd(client, analyst_headers):
    response = client.get(ENDPOINT, headers=analyst_headers)
    data = response.get_json()["data"]

    forbidden_keys = {"nome", "name", "nome_paciente", "patient_name"}
    for patient in data:
        present = forbidden_keys & set(patient.keys())
        assert present == set(), f"Campo de nome presente na resposta: {present}"


def test_campo1_is_null(client, analyst_headers):
    response = client.get(ENDPOINT, headers=analyst_headers)
    data = response.get_json()["data"]

    for patient in data:
        assert patient["campo1"] is None


def test_only_active_admissions(client, analyst_headers):
    response = client.get(ENDPOINT, headers=analyst_headers)
    data = response.get_json()["data"]

    ids = [p["id"] for p in data]
    assert _ADM_ACTIVE_UTI in ids
    assert _ADM_ACTIVE_ENF in ids
    assert _ADM_DISCHARGED not in ids


def test_nome_setor_via_join(client, analyst_headers):
    response = client.get(ENDPOINT, headers=analyst_headers)
    data = response.get_json()["data"]

    uti = _find_patient(data, _ADM_ACTIVE_UTI)
    enf = _find_patient(data, _ADM_ACTIVE_ENF)

    assert uti is not None
    assert uti["nome_setor"] == "UTI Adulto Teste"
    assert enf is not None
    assert enf["nome_setor"] == "Enfermaria Teste"


def test_protocolo_derivation(client, analyst_headers):
    response = client.get(ENDPOINT, headers=analyst_headers)
    data = response.get_json()["data"]

    uti = _find_patient(data, _ADM_ACTIVE_UTI)
    enf = _find_patient(data, _ADM_ACTIVE_ENF)

    assert uti["protocolo"] == "MNUTRIC"
    assert uti["ala"] == "UTI"

    assert enf["protocolo"] == "NRS2002"
    assert enf["ala"] == "Enfermaria"


def test_imc_calculation(client, analyst_headers):
    response = client.get(ENDPOINT, headers=analyst_headers)
    data = response.get_json()["data"]

    uti = _find_patient(data, _ADM_ACTIVE_UTI)
    assert uti["peso"] == 58.0
    assert uti["imc"] is not None
    assert 17.0 <= uti["imc"] <= 17.5

    enf = _find_patient(data, _ADM_ACTIVE_ENF)
    assert enf["peso"] == 65.0
    assert enf["imc"] is not None
    assert 25.0 <= enf["imc"] <= 26.0


def test_haval_calculation(client, analyst_headers):
    response = client.get(ENDPOINT, headers=analyst_headers)
    data = response.get_json()["data"]

    uti = _find_patient(data, _ADM_ACTIVE_UTI)
    assert uti["haval"] is not None
    assert 2.5 <= uti["haval"] <= 4.0

    enf = _find_patient(data, _ADM_ACTIVE_ENF)
    assert enf["haval"] is None


def test_d7_calculation(client, analyst_headers):
    response = client.get(ENDPOINT, headers=analyst_headers)
    data = response.get_json()["data"]

    uti = _find_patient(data, _ADM_ACTIVE_UTI)
    assert uti["d7"] is True

    enf = _find_patient(data, _ADM_ACTIVE_ENF)
    assert enf["d7"] is False


def _expected_age(birth_str):
    """Calculate expected age in complete years from a YYYY-MM-DD birthdate."""
    bd = date.fromisoformat(birth_str)
    today = date.today()
    return today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day))


def test_idade_and_dias(client, analyst_headers):
    response = client.get(ENDPOINT, headers=analyst_headers)
    data = response.get_json()["data"]

    uti = _find_patient(data, _ADM_ACTIVE_UTI)
    assert uti["idade"] == _expected_age("1959-03-15")
    assert uti["dias"] == 14

    enf = _find_patient(data, _ADM_ACTIVE_ENF)
    assert enf["idade"] == _expected_age("1990-08-22")
    assert enf["dias"] == 5


def test_conduta_and_sev(client, analyst_headers):
    response = client.get(ENDPOINT, headers=analyst_headers)
    data = response.get_json()["data"]

    uti = _find_patient(data, _ADM_ACTIVE_UTI)
    assert uti["conduta"] == "Dieta hipercalorica"
    assert uti["sev"] == "al"

    enf = _find_patient(data, _ADM_ACTIVE_ENF)
    assert enf["conduta"] is None
    assert enf["sev"] == "bx"


def test_default_null_fields(client, analyst_headers):
    response = client.get(ENDPOINT, headers=analyst_headers)
    data = response.get_json()["data"]

    for patient in data:
        assert patient["campo1"] is None
        assert isinstance(patient["hist"], list)
        assert isinstance(patient["glim_fen"], list)
        assert isinstance(patient["glim_etiol"], list)
        assert isinstance(patient["inst"], list)


def test_filter_by_setor(client, analyst_headers):
    response = client.get(
        f"{ENDPOINT}?setor={_SETOR_UTI}", headers=analyst_headers
    )
    data = response.get_json()["data"]

    assert response.status_code == 200
    assert len(data) >= 1
    for p in data:
        assert p["fksetor"] == _SETOR_UTI


def test_filter_by_setor_empty(client, analyst_headers):
    response = client.get(f"{ENDPOINT}?setor=999999", headers=analyst_headers)

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data == []


def test_filter_by_ala_uti(client, analyst_headers):
    response = client.get(f"{ENDPOINT}?ala=UTI", headers=analyst_headers)
    data = response.get_json()["data"]

    assert response.status_code == 200
    assert len(data) >= 1
    for p in data:
        assert p["ala"] == "UTI"
        assert p["protocolo"] == "MNUTRIC"


def test_filter_by_ala_enfermaria(client, analyst_headers):
    response = client.get(f"{ENDPOINT}?ala=Enfermaria", headers=analyst_headers)
    data = response.get_json()["data"]

    assert response.status_code == 200
    assert len(data) >= 1
    for p in data:
        assert p["ala"] == "Enfermaria"
        assert p["protocolo"] == "NRS2002"


def test_filter_setor_and_ala_combined(client, analyst_headers):
    response = client.get(
        f"{ENDPOINT}?setor={_SETOR_UTI}&ala=UTI", headers=analyst_headers
    )
    data = response.get_json()["data"]

    assert response.status_code == 200
    for p in data:
        assert p["fksetor"] == _SETOR_UTI
        assert p["ala"] == "UTI"


def test_response_total_field(client, analyst_headers):
    response = client.get(ENDPOINT, headers=analyst_headers)
    body = response.get_json()

    assert "total" in body
    assert body["total"] == len(body["data"])


def test_response_total_matches_filter(client, analyst_headers):
    response = client.get(
        f"{ENDPOINT}?setor={_SETOR_UTI}", headers=analyst_headers
    )
    body = response.get_json()

    assert body["total"] == len(body["data"])
    assert body["total"] >= 1


def test_filter_empty_result_has_total_zero(client, analyst_headers):
    response = client.get(f"{ENDPOINT}?setor=999999", headers=analyst_headers)
    body = response.get_json()

    assert response.status_code == 200
    assert body["data"] == []
    assert body["total"] == 0


def test_response_envelope_structure(client, analyst_headers):
    response = client.get(ENDPOINT, headers=analyst_headers)
    body = response.get_json()

    assert set(body.keys()) == {"status", "data", "total"}
    assert body["status"] == "success"
    assert isinstance(body["data"], list)
    assert isinstance(body["total"], int)


def test_glim_fields_populated(client, analyst_headers):
    response = client.get(ENDPOINT, headers=analyst_headers)
    data = response.get_json()["data"]

    uti = _find_patient(data, _ADM_ACTIVE_UTI)
    assert uti is not None

    assert uti["glim_diag"] == "mod"
    assert "perda_peso" in uti["glim_fen"]
    assert "baixo_imc" in uti["glim_fen"]
    assert "inflamacao" in uti["glim_etiol"]


def test_glim_defaults_when_no_data(client, analyst_headers):
    response = client.get(ENDPOINT, headers=analyst_headers)
    data = response.get_json()["data"]

    enf = _find_patient(data, _ADM_ACTIVE_ENF)
    assert enf is not None

    assert enf["glim_diag"] is None
    assert enf["glim_fen"] == []
    assert enf["glim_etiol"] == []


def test_imc_null_when_data_missing(client, analyst_headers):
    response = client.get(ENDPOINT, headers=analyst_headers)
    data = response.get_json()["data"]

    no_weight = _find_patient(data, _ADM_NO_WEIGHT)
    assert no_weight is not None
    assert no_weight["imc"] is None
    assert no_weight["peso"] is None


def test_no_weight_patient_is_active(client, analyst_headers):
    response = client.get(ENDPOINT, headers=analyst_headers)
    data = response.get_json()["data"]

    ids = [p["id"] for p in data]
    assert _ADM_NO_WEIGHT in ids


def test_field_types_validation(client, analyst_headers):
    response = client.get(ENDPOINT, headers=analyst_headers)
    data = response.get_json()["data"]

    uti = _find_patient(data, _ADM_ACTIVE_UTI)
    assert uti is not None

    assert isinstance(uti["id"], int)
    assert isinstance(uti["fksetor"], int)
    assert isinstance(uti["idade"], int)
    assert isinstance(uti["dias"], int)
    assert isinstance(uti["pri"], int)

    assert isinstance(uti["leito"], str)
    assert isinstance(uti["ala"], str)
    assert isinstance(uti["nome_setor"], str)
    assert isinstance(uti["protocolo"], str)
    assert isinstance(uti["sev"], str)

    assert isinstance(uti["peso"], (int, float))
    assert isinstance(uti["imc"], (int, float))
    assert isinstance(uti["haval"], (int, float))

    assert isinstance(uti["al_ok"], bool)
    assert isinstance(uti["d7"], bool)

    assert isinstance(uti["glim_fen"], list)
    assert isinstance(uti["glim_etiol"], list)
    assert isinstance(uti["inst"], list)
    assert isinstance(uti["hist"], list)


def test_nullable_fields_allow_none(client, analyst_headers):
    response = client.get(ENDPOINT, headers=analyst_headers)
    data = response.get_json()["data"]

    enf = _find_patient(data, _ADM_ACTIVE_ENF)
    assert enf is not None

    assert enf["haval"] is None
    assert enf["conduta"] is None
    assert enf["glim_diag"] is None
    assert enf["dieta"] is None
    assert enf["npo"] is None
    assert enf["alergia"] is None
    assert enf["campo1"] is None


def test_al_ok_true_when_alergia_null(client, analyst_headers):
    response = client.get(ENDPOINT, headers=analyst_headers)
    data = response.get_json()["data"]

    for patient in data:
        assert patient["alergia"] is None
        assert patient["al_ok"] is True


def test_pri_field_is_positive_integer(client, analyst_headers):
    response = client.get(ENDPOINT, headers=analyst_headers)
    data = response.get_json()["data"]

    for patient in data:
        assert isinstance(patient["pri"], int)
        assert patient["pri"] >= 1


def test_pri_field_sequential(client, analyst_headers):
    response = client.get(ENDPOINT, headers=analyst_headers)
    data = response.get_json()["data"]

    pris = sorted([p["pri"] for p in data])
    expected = list(range(1, len(data) + 1))
    assert pris == expected


def test_dieta_npo_null_this_us(client, analyst_headers):
    response = client.get(ENDPOINT, headers=analyst_headers)
    data = response.get_json()["data"]

    for patient in data:
        assert patient["dieta"] is None
        assert patient["npo"] is None


def test_hist_empty_when_no_assessment(client, analyst_headers):
    response = client.get(ENDPOINT, headers=analyst_headers)
    data = response.get_json()["data"]

    enf = _find_patient(data, _ADM_ACTIVE_ENF)
    assert enf is not None
    assert enf["hist"] == []


def test_inst_empty_this_us(client, analyst_headers):
    response = client.get(ENDPOINT, headers=analyst_headers)
    data = response.get_json()["data"]

    for patient in data:
        assert patient["inst"] == []


def test_filter_ala_case_insensitive(client, analyst_headers):
    response_upper = client.get(f"{ENDPOINT}?ala=UTI", headers=analyst_headers)
    response_lower = client.get(f"{ENDPOINT}?ala=uti", headers=analyst_headers)

    data_upper = response_upper.get_json()["data"]
    data_lower = response_lower.get_json()["data"]

    assert response_upper.status_code == 200
    assert response_lower.status_code == 200
    assert len(data_upper) == len(data_lower)

    ids_upper = sorted([p["id"] for p in data_upper])
    ids_lower = sorted([p["id"] for p in data_lower])
    assert ids_upper == ids_lower

