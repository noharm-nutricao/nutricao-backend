"""Integration tests for GET /patients — US-BE-08.

Seed triagem data (admissions 1–5):
  1: MNUTRIC, classificacao=cr, sev=cr, pri=1, nrs_completo=True, dados_incompletos=False
  2: MNUTRIC, classificacao=al, sev=al, pri=3, nrs_completo=True, dados_incompletos=False
  3: NRS2002,  classificacao=al, sev=al, pri=4, nrs_completo=True, dados_incompletos=False
  5: NRS2002,  classificacao=bx, sev=bx, pri=5, nrs_completo=False, dados_incompletos=False
  4: MNUTRIC,  classificacao='', sev='',  pri=6, nrs_completo=False, dados_incompletos=True
All other active admissions (6-10, …) have no triagem row.
"""

import pytest
from sqlalchemy import text

from tests.conftest import session, session_commit

_TEST_ADMS = [1, 2, 3, 4, 5]

URL = "/patients"


@pytest.fixture(scope="module", autouse=True)
def setup_patients_listing_module():
    _ensure_triagem_table()
    _cleanup()
    _seed()
    yield
    _cleanup()


def _ensure_triagem_table():
    session.execute(
        text(
            """CREATE TABLE IF NOT EXISTS demo.triagem (
                nratendimento BIGINT PRIMARY KEY,
                protocolo VARCHAR(10),
                mnutric_total SMALLINT,
                mn_dims JSONB,
                mn_apache_manual BOOLEAN,
                mn_sofa_manual BOOLEAN,
                dados_incompletos BOOLEAN,
                nrs_total SMALLINT,
                nrs_dims JSONB,
                nrs_nut SMALLINT,
                nrs_completo BOOLEAN,
                classificacao VARCHAR(3),
                sev VARCHAR(3),
                pri SMALLINT,
                haval SMALLINT,
                d7 BOOLEAN,
                calculado_at TIMESTAMP,
                update_at TIMESTAMP
            )"""
        )
    )
    session_commit()


def _cleanup():
    session.execute(
        text("DELETE FROM demo.triagem WHERE nratendimento = ANY(:adms)"),
        {"adms": _TEST_ADMS},
    )
    session_commit()


def _seed():
    rows = [
        (1, "MNUTRIC", 7, '{"apache":2,"sofa":1,"idade":2,"comor":1,"dias":1}', True, True, False, 3, '{"nut":1,"doenca":1,"idade":1}', 1, True,  "cr", "cr", 1),
        (2, "MNUTRIC", 5, '{"apache":2,"sofa":1,"idade":1,"comor":1,"dias":0}', True, True, False, 2, '{"nut":1,"doenca":1,"idade":0}', 1, True,  "al", "al", 3),
        (3, "NRS2002", 0, None,                                                  False, False, False, 4, '{"nut":2,"doenca":2,"idade":0}', 2, True,  "al", "al", 4),
        (5, "NRS2002", 0, None,                                                  False, False, False, 2, '{"nut":1,"doenca":1,"idade":0}', 1, False, "bx", "bx", 5),
        (4, "MNUTRIC", 0, '{"apache":0,"sofa":0,"idade":0,"comor":0,"dias":0}', False, False, True,  0, None,                             0, False, "",   "",   6),
    ]
    for adm, prot, mn_total, mn_dims, mn_ap_m, mn_s_m, dados_inc, nrs_total, nrs_dims, nrs_nut, nrs_comp, classif, sev, pri in rows:
        session.execute(
            text(
                """INSERT INTO demo.triagem
                   (nratendimento, protocolo, mnutric_total, mn_dims,
                    mn_apache_manual, mn_sofa_manual, dados_incompletos,
                    nrs_total, nrs_dims, nrs_nut, nrs_completo,
                    classificacao, sev, pri)
                   VALUES (:adm, :prot, :mn_total, CAST(:mn_dims AS JSONB),
                           :mn_ap_m, :mn_s_m, :dados_inc,
                           :nrs_total, CAST(:nrs_dims AS JSONB), :nrs_nut, :nrs_comp,
                           :classif, :sev, :pri)"""
            ),
            {
                "adm": adm, "prot": prot, "mn_total": mn_total, "mn_dims": mn_dims,
                "mn_ap_m": mn_ap_m, "mn_s_m": mn_s_m, "dados_inc": dados_inc,
                "nrs_total": nrs_total, "nrs_dims": nrs_dims, "nrs_nut": nrs_nut,
                "nrs_comp": nrs_comp, "classif": classif, "sev": sev, "pri": pri,
            },
        )
    session_commit()

CAMPO1_REQUIRED_FIELDS = {
    "protocolo",
    "mnutric_total",
    "mn_dims",
    "mn_apache_manual",
    "mn_sofa_manual",
    "dados_incompletos",
    "nrs_total",
    "nrs_dims",
    "nrs_completo",
    "classificacao",
    "calculado_at",
}


def test_get_patients_returns_200(client, analyst_headers):
    """GET /patients — deve retornar 200 para usuário autenticado."""
    response = client.get(URL, headers=analyst_headers)
    assert response.status_code == 200


def test_ordering_first_patient_is_highest_priority(client, analyst_headers):
    """GET /patients — primeiro paciente deve ter sev='cr' (maior prioridade, pri=1)."""
    response = client.get(URL, headers=analyst_headers)
    data = response.get_json()["data"]

    assert len(data) > 0
    first = data[0]
    assert first["id"] == 1
    assert first["sev"] == "cr"
    assert first["pri"] == 1


def test_campo1_schema_is_complete_for_triagem_patient(client, analyst_headers):
    """GET /patients — paciente com triagem deve ter todos os campos de campo1."""
    response = client.get(URL, headers=analyst_headers)
    data = response.get_json()["data"]

    first = next(p for p in data if p["id"] == 1)
    assert first["campo1"] is not None
    assert CAMPO1_REQUIRED_FIELDS.issubset(first["campo1"].keys())


def test_campo1_protocolo_mnutric_on_admission1(client, analyst_headers):
    """GET /patients — admissão 1 deve ter protocolo MNUTRIC no campo1."""
    response = client.get(URL, headers=analyst_headers)
    data = response.get_json()["data"]

    patient = next(p for p in data if p["id"] == 1)
    assert patient["protocolo"] == "MNUTRIC"
    assert patient["campo1"]["protocolo"] == "MNUTRIC"


def test_nrs_completo_false_when_no_nutricional_nrs(client, analyst_headers):
    """GET /patients — admissão 5 não tem registro em nutricional_nrs, nrs_completo deve ser False."""
    response = client.get(URL, headers=analyst_headers)
    data = response.get_json()["data"]

    patient5 = next((p for p in data if p["id"] == 5), None)
    assert patient5 is not None
    assert patient5["campo1"]["nrs_completo"] is False


def test_dados_incompletos_true_for_admission4(client, analyst_headers):
    """GET /patients — admissão 4 (UTI sem APACHE/SOFA) deve ter dados_incompletos=True."""
    response = client.get(URL, headers=analyst_headers)
    data = response.get_json()["data"]

    patient4 = next((p for p in data if p["id"] == 4), None)
    assert patient4 is not None
    assert patient4["campo1"]["dados_incompletos"] is True


def test_patient_without_triagem_has_null_campo1(client, analyst_headers):
    """GET /patients — paciente sem triagem deve ter campo1=None."""
    response = client.get(URL, headers=analyst_headers)
    data = response.get_json()["data"]

    patient6 = next((p for p in data if p["id"] == 6), None)
    assert patient6 is not None
    assert patient6["campo1"] is None
    assert patient6["sev"] is None
    assert patient6["pri"] is None


def test_no_nome_field_lgpd(client, analyst_headers):
    """GET /patients — resposta não deve conter campo 'nome' (LGPD)."""
    response = client.get(URL, headers=analyst_headers)
    data = response.get_json()["data"]

    for item in data:
        assert "nome" not in item


def test_patients_without_triagem_appear_last(client, analyst_headers):
    """GET /patients — pacientes sem triagem (pri=NULL) devem aparecer por último."""
    response = client.get(URL, headers=analyst_headers)
    data = response.get_json()["data"]

    first_null_pri_index = next(
        (i for i, p in enumerate(data) if p["pri"] is None), None
    )
    if first_null_pri_index is None:
        return
    for item in data[first_null_pri_index:]:
        assert item["pri"] is None