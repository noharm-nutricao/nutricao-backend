import json

import pytest
from sqlalchemy import text

from security.role import Role
from tests.conftest import get_access, make_headers, session, session_commit

_SETOR_UTI = 800
_SETOR_ENF = 801
_SEG_UTI = 800
_SEG_ENF = 801
_HOSPITAL = 1
_ADM_UTI = 800001
_ADM_ENF = 800002
_ADM_NOT_FOUND = 999999


def _endpoint(nratendimento):
    return f"/nutritional/patients/{nratendimento}/nrs-nut"


@pytest.fixture(scope="module", autouse=True)
def setup_nrs_nut_module():
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


def _ensure_schema():
    session.execute(
        text("ALTER TABLE demo.pessoa ADD COLUMN IF NOT EXISTS fksetor BIGINT")
    )
    session.execute(
        text("ALTER TABLE demo.pessoa ADD COLUMN IF NOT EXISTS leito VARCHAR(16)")
    )
    session.execute(
        text("ALTER TABLE demo.pessoa ADD COLUMN IF NOT EXISTS idcid VARCHAR(10)")
    )

    session.execute(
        text(
            """CREATE TABLE IF NOT EXISTS demo.nutricional_triagem (
                idnutricional_triagem BIGSERIAL PRIMARY KEY,
                nratendimento BIGINT NOT NULL,
                classificacao TEXT,
                mn_apache INTEGER,
                mn_sofa INTEGER,
                mn_apache_manual BOOLEAN,
                mn_sofa_manual BOOLEAN,
                nrs_nut INTEGER,
                nrs_doenca INTEGER,
                nrs_idade INTEGER,
                nrs_completo BOOLEAN,
                mnutric_total INTEGER,
                dados_incompletos BOOLEAN,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                created_by BIGINT NOT NULL DEFAULT 1,
                updated_at TIMESTAMP,
                updated_by BIGINT
            )"""
        )
    )

    session_commit()


def _seed():
    session.execute(
        text(
            "INSERT INTO demo.segmento (idsegmento, nome, status, tp_segmento, cpoe, cpoe_ambulatorio) "
            "VALUES (:id, :nome, 1, :tp, false, false) ON CONFLICT DO NOTHING"
        ),
        {"id": _SEG_UTI, "nome": "Seg UTI NRS", "tp": 3},
    )
    session.execute(
        text(
            "INSERT INTO demo.segmento (idsegmento, nome, status, tp_segmento, cpoe, cpoe_ambulatorio) "
            "VALUES (:id, :nome, 1, :tp, false, false) ON CONFLICT DO NOTHING"
        ),
        {"id": _SEG_ENF, "nome": "Seg Enf NRS", "tp": 2},
    )

    session.execute(
        text(
            "INSERT INTO demo.setor (fksetor, fkhospital, nome) "
            "VALUES (:id, :hosp, :nome) ON CONFLICT DO NOTHING"
        ),
        {"id": _SETOR_UTI, "hosp": _HOSPITAL, "nome": "UTI NRS Teste"},
    )
    session.execute(
        text(
            "INSERT INTO demo.setor (fksetor, fkhospital, nome) "
            "VALUES (:id, :hosp, :nome) ON CONFLICT DO NOTHING"
        ),
        {"id": _SETOR_ENF, "hosp": _HOSPITAL, "nome": "Enfermaria NRS Teste"},
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
            " sexo, peso, altura, fksetor, leito, idcid) "
            "VALUES (:pk, :hosp, :adm, NOW() - INTERVAL '10 days', '1955-06-20', "
            " 'M', 72.0, 175.0, :setor, 'UTI-01', 'J18.9')"
        ),
        {
            "pk": _ADM_UTI,
            "hosp": _HOSPITAL,
            "adm": _ADM_UTI,
            "setor": _SETOR_UTI,
        },
    )

    session.execute(
        text(
            "INSERT INTO demo.pessoa "
            "(fkpessoa, fkhospital, nratendimento, dtinternacao, dtnascimento, "
            " sexo, peso, altura, fksetor, leito) "
            "VALUES (:pk, :hosp, :adm, NOW() - INTERVAL '3 days', '1990-01-10', "
            " 'F', 60.0, 165.0, :setor, 'ENF-01')"
        ),
        {
            "pk": _ADM_ENF,
            "hosp": _HOSPITAL,
            "adm": _ADM_ENF,
            "setor": _SETOR_ENF,
        },
    )

    session_commit()


def _cleanup():
    session.execute(
        text("DELETE FROM demo.nutricional_triagem WHERE nratendimento >= 800000")
    )
    session.execute(text("DELETE FROM demo.pessoa WHERE nratendimento >= 800000"))
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


def _get_triagem_row(nratendimento):
    row = session.execute(
        text(
            "SELECT mn_apache, mn_sofa, mn_apache_manual, mn_sofa_manual, "
            "mnutric_total, dados_incompletos, nrs_completo "
            "FROM demo.nutricional_triagem WHERE nratendimento = :adm "
            "ORDER BY created_at DESC LIMIT 1"
        ),
        {"adm": nratendimento},
    ).fetchone()
    session_commit()
    return row


def test_200_success(client, analyst_headers):
    response = client.put(
        _endpoint(_ADM_UTI),
        data=json.dumps({"apache_ii": 22, "sofa": 8}),
        headers=analyst_headers,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "success"
    campo1 = body["data"]["campo1"]
    assert campo1["protocolo"] == "MNUTRIC"
    assert campo1["mn_apache_manual"] is True
    assert campo1["mn_sofa_manual"] is True
    assert campo1["dados_incompletos"] is False
    assert isinstance(campo1["mnutric_total"], int)


def test_200_persists_in_db(client, analyst_headers):
    client.put(
        _endpoint(_ADM_UTI),
        data=json.dumps({"apache_ii": 18, "sofa": 12}),
        headers=analyst_headers,
    )

    row = _get_triagem_row(_ADM_UTI)
    assert row is not None
    assert row[0] == 1   # mn_apache dimension score: apache_ii=18 → 1 (15≤18<24)
    assert row[1] == 2   # mn_sofa dimension score: sofa=12 → 2 (≥10)
    assert row[2] is True
    assert row[3] is True


def test_200_mnutric_recalculated(client, analyst_headers):
    response = client.put(
        _endpoint(_ADM_UTI),
        data=json.dumps({"apache_ii": 22, "sofa": 8}),
        headers=analyst_headers,
    )

    body = response.get_json()
    campo1 = body["data"]["campo1"]

    assert campo1["mnutric_total"] == campo1["mn_dims"]["idade"] + \
        campo1["mn_dims"]["apache"] + campo1["mn_dims"]["sofa"] + \
        campo1["mn_dims"]["comor"] + campo1["mn_dims"]["dias"]


def test_200_mn_dims_structure(client, analyst_headers):
    response = client.put(
        _endpoint(_ADM_UTI),
        data=json.dumps({"apache_ii": 22, "sofa": 8}),
        headers=analyst_headers,
    )

    campo1 = response.get_json()["data"]["campo1"]
    mn_dims = campo1["mn_dims"]

    assert set(mn_dims.keys()) == {"idade", "apache", "sofa", "comor", "dias"}
    for v in mn_dims.values():
        assert isinstance(v, int)
        assert v >= 0


def test_200_nrs_dims_structure(client, analyst_headers):
    response = client.put(
        _endpoint(_ADM_UTI),
        data=json.dumps({"apache_ii": 22, "sofa": 8}),
        headers=analyst_headers,
    )

    campo1 = response.get_json()["data"]["campo1"]
    nrs_dims = campo1["nrs_dims"]

    assert set(nrs_dims.keys()) == {"nut", "doenca", "idade"}
    for v in nrs_dims.values():
        assert isinstance(v, int)
        assert v >= 0


def test_200_nrs_total_present(client, analyst_headers):
    response = client.put(
        _endpoint(_ADM_UTI),
        data=json.dumps({"apache_ii": 10, "sofa": 3}),
        headers=analyst_headers,
    )

    campo1 = response.get_json()["data"]["campo1"]
    assert isinstance(campo1["nrs_total"], int)
    assert isinstance(campo1["nrs_completo"], bool)


def test_200_classificacao_present(client, analyst_headers):
    response = client.put(
        _endpoint(_ADM_UTI),
        data=json.dumps({"apache_ii": 22, "sofa": 8}),
        headers=analyst_headers,
    )

    campo1 = response.get_json()["data"]["campo1"]
    assert campo1["classificacao"] in ("cr", "md", "bx")


def test_200_idempotent(client, analyst_headers):
    payload = json.dumps({"apache_ii": 22, "sofa": 8})

    r1 = client.put(_endpoint(_ADM_UTI), data=payload, headers=analyst_headers)
    r2 = client.put(_endpoint(_ADM_UTI), data=payload, headers=analyst_headers)

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.get_json()["data"]["campo1"]["mnutric_total"] == \
        r2.get_json()["data"]["campo1"]["mnutric_total"]


def test_401_no_token(client):
    response = client.put(
        _endpoint(_ADM_UTI),
        data=json.dumps({"apache_ii": 22, "sofa": 8}),
        content_type="application/json",
    )

    assert response.status_code == 401


def test_401_no_permission(client, viewer_headers):
    response = client.put(
        _endpoint(_ADM_UTI),
        data=json.dumps({"apache_ii": 22, "sofa": 8}),
        headers=viewer_headers,
    )

    assert response.status_code == 401


def test_400_apache_out_of_range_high(client, analyst_headers):
    response = client.put(
        _endpoint(_ADM_UTI),
        data=json.dumps({"apache_ii": 72, "sofa": 8}),
        headers=analyst_headers,
    )

    assert response.status_code == 400


def test_400_apache_out_of_range_negative(client, analyst_headers):
    response = client.put(
        _endpoint(_ADM_UTI),
        data=json.dumps({"apache_ii": -1, "sofa": 8}),
        headers=analyst_headers,
    )

    assert response.status_code == 400


def test_400_sofa_out_of_range_high(client, analyst_headers):
    response = client.put(
        _endpoint(_ADM_UTI),
        data=json.dumps({"apache_ii": 22, "sofa": 25}),
        headers=analyst_headers,
    )

    assert response.status_code == 400


def test_400_sofa_out_of_range_negative(client, analyst_headers):
    response = client.put(
        _endpoint(_ADM_UTI),
        data=json.dumps({"apache_ii": 22, "sofa": -1}),
        headers=analyst_headers,
    )

    assert response.status_code == 400


def test_400_missing_apache(client, analyst_headers):
    response = client.put(
        _endpoint(_ADM_UTI),
        data=json.dumps({"sofa": 8}),
        headers=analyst_headers,
    )

    assert response.status_code == 400


def test_400_missing_sofa(client, analyst_headers):
    response = client.put(
        _endpoint(_ADM_UTI),
        data=json.dumps({"apache_ii": 22}),
        headers=analyst_headers,
    )

    assert response.status_code == 400


def test_400_nrs_nut_forbidden(client, analyst_headers):
    response = client.put(
        _endpoint(_ADM_UTI),
        data=json.dumps({"apache_ii": 22, "sofa": 8, "nrs_nut": 3}),
        headers=analyst_headers,
    )

    assert response.status_code == 400


def test_400_invalid_type_string(client, analyst_headers):
    response = client.put(
        _endpoint(_ADM_UTI),
        data=json.dumps({"apache_ii": "abc", "sofa": 8}),
        headers=analyst_headers,
    )

    assert response.status_code == 400


def test_400_apache_boundary_valid_zero(client, analyst_headers):
    response = client.put(
        _endpoint(_ADM_UTI),
        data=json.dumps({"apache_ii": 0, "sofa": 0}),
        headers=analyst_headers,
    )

    assert response.status_code == 200


def test_400_apache_boundary_valid_max(client, analyst_headers):
    response = client.put(
        _endpoint(_ADM_UTI),
        data=json.dumps({"apache_ii": 71, "sofa": 24}),
        headers=analyst_headers,
    )

    assert response.status_code == 200


def test_404_patient_not_found(client, analyst_headers):
    response = client.put(
        _endpoint(_ADM_NOT_FOUND),
        data=json.dumps({"apache_ii": 22, "sofa": 8}),
        headers=analyst_headers,
    )

    assert response.status_code == 404


def test_422_patient_not_uti(client, analyst_headers):
    response = client.put(
        _endpoint(_ADM_ENF),
        data=json.dumps({"apache_ii": 22, "sofa": 8}),
        headers=analyst_headers,
    )

    assert response.status_code == 422


def test_campo1_complete_structure(client, analyst_headers):
    response = client.put(
        _endpoint(_ADM_UTI),
        data=json.dumps({"apache_ii": 22, "sofa": 8}),
        headers=analyst_headers,
    )

    campo1 = response.get_json()["data"]["campo1"]
    expected_keys = {
        "protocolo", "mnutric_total", "mn_dims",
        "mn_apache_manual", "mn_sofa_manual", "dados_incompletos",
        "nrs_total", "nrs_dims", "nrs_completo", "classificacao",
    }
    assert set(campo1.keys()) == expected_keys


def test_flags_after_save(client, analyst_headers):
    response = client.put(
        _endpoint(_ADM_UTI),
        data=json.dumps({"apache_ii": 15, "sofa": 6}),
        headers=analyst_headers,
    )

    campo1 = response.get_json()["data"]["campo1"]
    assert campo1["mn_apache_manual"] is True
    assert campo1["mn_sofa_manual"] is True
    assert campo1["dados_incompletos"] is False


def test_nrs_not_affected_by_endpoint(client, analyst_headers):
    session.execute(
        text(
            "UPDATE demo.nutricional_triagem SET nrs_nut = 2, nrs_doenca = 1, "
            "nrs_completo = true WHERE nratendimento = :adm"
        ),
        {"adm": _ADM_UTI},
    )
    session_commit()

    response = client.put(
        _endpoint(_ADM_UTI),
        data=json.dumps({"apache_ii": 22, "sofa": 8}),
        headers=analyst_headers,
    )

    campo1 = response.get_json()["data"]["campo1"]
    assert campo1["nrs_dims"]["nut"] == 2
    assert campo1["nrs_dims"]["doenca"] == 1
    assert campo1["nrs_completo"] is True

