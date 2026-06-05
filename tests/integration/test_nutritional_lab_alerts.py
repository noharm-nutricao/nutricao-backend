import pytest
from sqlalchemy import text

from mobile import app
from models.main import db, dbSession
from services.nutritional.nutritional_lab_alert_service import process_lab_pending_alerts
from tests.conftest import session, session_commit
from tests.utils.utils_test_prescription import create_prescription

_ADM = 100777
_PERSON = 100777
_PRESC = 100777
_SEGMENT = 1

_fkexame_seq = [900700000]


def _prereqs_missing():
    aux = session.execute(
        text("SELECT to_regclass('demo.nutricional_aux_alerta')")
    ).scalar()
    trigger = session.execute(
        text("SELECT 1 FROM pg_trigger WHERE tgname = 'trg_cria_aux_alerta_exame'")
    ).scalar()
    has_fkexame = session.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = 'demo' AND table_name = 'nutricional_aux_alerta' "
            "AND column_name = 'fkexame'"
        )
    ).scalar()
    seed = session.execute(
        text(
            "SELECT 1 FROM demo.segmentoexame "
            "WHERE idsegmento = :seg AND upper(tpexame) = 'ALB'"
        ),
        {"seg": _SEGMENT},
    ).scalar()
    return not (aux and trigger and has_fkexame and seed)


@pytest.fixture(scope="module", autouse=True)
def setup_module():
    if _prereqs_missing():
        pytest.skip("Migrations V6/V7 ausentes no banco de teste (aux_alerta/trigger/seed)")
    _cleanup()
    session.execute(
        text(
            "INSERT INTO demo.pessoa (fkpessoa, fkhospital, nratendimento, dtinternacao) "
            "VALUES (:pk, 1, :adm, NOW() - INTERVAL '2 days') ON CONFLICT DO NOTHING"
        ),
        {"pk": _PERSON, "adm": _ADM},
    )
    session_commit()
    create_prescription(
        id=_PRESC, admissionNumber=_ADM, idPatient=_PERSON, idSegment=_SEGMENT
    )
    yield
    _cleanup()


@pytest.fixture(autouse=True)
def _clean_each():
    _clean_lab()
    yield


def _insert_exame(tpexame, resultado):
    _fkexame_seq[0] += 1
    session.execute(
        text(
            "INSERT INTO demo.exame "
            "(fkexame, fkpessoa, nratendimento, dtexame, tpexame, resultado, unidade) "
            "VALUES (:fk, :pp, :adm, NOW(), :tp, :res, 'x')"
        ),
        {"fk": _fkexame_seq[0], "pp": _PERSON, "adm": _ADM, "tp": tpexame, "res": resultado},
    )
    session_commit()


def _set_ne_npt_pos_npo():
    session.execute(text("SET session_replication_role = replica"))
    session.execute(
        text(
            "INSERT INTO demo.presmed "
            "(fkprescricao, fkmedicamento, status, origem, sonda, intravenosa, dtsuspensao) "
            "VALUES (:p, 1, '0', 'Dietas', false, false, NOW())"
        ),
        {"p": _PRESC},
    )
    session.execute(
        text(
            "INSERT INTO demo.presmed "
            "(fkprescricao, fkmedicamento, status, origem, sonda, intravenosa, dtsuspensao) "
            "VALUES (:p, 1, '0', 'Dietas', false, true, NULL)"
        ),
        {"p": _PRESC},
    )
    session.execute(text("SET session_replication_role = origin"))
    session_commit()


def _run_engine():
    with app.app_context():
        dbSession.setSchema("demo")
        process_lab_pending_alerts()
        db.session.commit()


def _active_lab_alerts():
    session_commit()
    return session.execute(
        text(
            "SELECT descricao, severidade FROM demo.nutricional_alerta "
            "WHERE nratendimento = :adm AND tipo = 'lab' AND ativo = true "
            "ORDER BY descricao"
        ),
        {"adm": _ADM},
    ).fetchall()


def _alert_by_descricao(descricao):
    session_commit()
    return session.execute(
        text(
            "SELECT severidade, ativo FROM demo.nutricional_alerta "
            "WHERE nratendimento = :adm AND tipo = 'lab' AND descricao = :d "
            "ORDER BY id DESC LIMIT 1"
        ),
        {"adm": _ADM, "d": descricao},
    ).fetchone()


def test_zero_alterados_nenhum_alerta():
    _insert_exame("K", 4.5)  # dentro do limite (3.5-5.1)
    _run_engine()
    assert _active_lab_alerts() == []


def test_um_alterado_md():
    _insert_exame("ALB", 2.0)  # < 3.5
    _run_engine()
    alertas = _active_lab_alerts()
    assert len(alertas) == 1
    assert alertas[0].descricao == "Albumina"
    assert alertas[0].severidade == "md"


def test_dois_alterados_al():
    _insert_exame("ALB", 2.0)
    _insert_exame("HB", 8.0)  # < 12
    _run_engine()
    alertas = _active_lab_alerts()
    assert {a.descricao for a in alertas} == {"Albumina", "Hemoglobina"}
    assert {a.severidade for a in alertas} == {"al"}


def test_fosforo_npt_cr():
    _set_ne_npt_pos_npo()
    try:
        _insert_exame("P", 1.0)  # fosforo < 2.5
        _run_engine()
        fosforo = _alert_by_descricao("Fosforo")
        assert fosforo is not None
        assert fosforo.ativo is True
        assert fosforo.severidade == "cr"
    finally:
        session.execute(
            text("DELETE FROM demo.presmed WHERE fkprescricao = :p"), {"p": _PRESC}
        )
        session_commit()


def test_exame_normaliza_ativo_false():
    _insert_exame("ALB", 2.0)
    _run_engine()
    assert _alert_by_descricao("Albumina").ativo is True

    _insert_exame("ALB", 4.0)  # normalizou (>= 3.5)
    _run_engine()
    assert _alert_by_descricao("Albumina").ativo is False


def _clean_lab():
    session.execute(
        text("DELETE FROM demo.nutricional_alerta WHERE nratendimento = :adm"),
        {"adm": _ADM},
    )
    session.execute(
        text("DELETE FROM demo.nutricional_aux_alerta WHERE nratendimento = :adm"),
        {"adm": _ADM},
    )
    session.execute(
        text("DELETE FROM demo.exame WHERE nratendimento = :adm"), {"adm": _ADM}
    )
    session_commit()


def _cleanup():
    _clean_lab()
    session.execute(
        text("DELETE FROM demo.presmed WHERE fkprescricao = :p"), {"p": _PRESC}
    )
    session.execute(
        text("DELETE FROM demo.prescricao WHERE fkprescricao = :p"), {"p": _PRESC}
    )
    session.execute(
        text("DELETE FROM demo.pessoa WHERE nratendimento = :adm"), {"adm": _ADM}
    )
    session_commit()
