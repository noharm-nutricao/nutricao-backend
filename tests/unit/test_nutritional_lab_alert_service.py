from types import SimpleNamespace
from unittest.mock import patch

import pytest

from services.nutritional import nutritional_lab_alert_service as svc

LIMITS = {
    "ALB": (3.5, 5.2),
    "HB": (12.0, 17.0),
    "P": (2.5, 4.5),
    "MG": (1.7, 2.4),
    "K": (3.5, 5.1),
    "PCR": (0.0, 0.5),
}


@pytest.mark.parametrize(
    "qtd,fosforo_magnesio,ne_npt,esperado",
    [
        (0, False, False, None),
        (1, False, False, "md"),
        (2, False, False, "al"),
        (3, False, False, "cr"),
        (1, True, True, "cr"),
        (1, True, False, "md"),
        (2, False, True, "al"),
    ],
)
def test_resolver_severidade(qtd, fosforo_magnesio, ne_npt, esperado):
    assert svc.resolver_severidade(qtd, fosforo_magnesio, ne_npt) == esperado


def test_is_exame_alterado_abaixo_do_limite():
    assert svc.is_exame_alterado("ALB", 3.0, 3.5, 5.2) is True
    assert svc.is_exame_alterado("ALB", 4.0, 3.5, 5.2) is False


def test_is_exame_alterado_pcr_acima_do_limite():
    assert svc.is_exame_alterado("PCR", 1.0, 0.0, 0.5) is True
    assert svc.is_exame_alterado("PCR", 0.2, 0.0, 0.5) is False


def test_is_exame_alterado_resultado_nulo():
    assert svc.is_exame_alterado("ALB", None, 3.5, 5.2) is False


class FakeAlert:
    def __init__(self, descricao, severidade=None, ativo=True):
        self.descricao = descricao
        self.severidade = severidade
        self.ativo = ativo


@pytest.fixture
def repo(monkeypatch):
    state = {"created": [], "active": [], "ne_npt": False}
    m = svc.nutritional_repository

    monkeypatch.setattr(m, "get_patient_segment_id", lambda nra: 1)
    monkeypatch.setattr(
        m,
        "get_exam_limit",
        lambda idseg, tp: SimpleNamespace(
            min=LIMITS[tp.upper()][0], max=LIMITS[tp.upper()][1]
        ),
    )
    monkeypatch.setattr(m, "get_active_lab_alerts", lambda nra: list(state["active"]))
    monkeypatch.setattr(m, "get_ne_npt_pos_npo", lambda nra: state["ne_npt"])

    def _create(nra, descricao, sev):
        alerta = FakeAlert(descricao, sev, True)
        state["created"].append(alerta)
        state["active"].append(alerta)
        return alerta

    monkeypatch.setattr(m, "create_lab_alert", _create)
    monkeypatch.setattr(m, "deactivate_lab_alert", lambda a: setattr(a, "ativo", False))
    monkeypatch.setattr(m, "set_lab_severity", lambda a, sev: setattr(a, "severidade", sev))
    return state


def _exames(monkeypatch, exames):
    monkeypatch.setattr(
        svc.nutritional_repository, "get_latest_monitored_exams", lambda nra: exames
    )


def test_calc_zero_alterados(repo, monkeypatch):
    _exames(monkeypatch, {"ALB": 4.0, "HB": 14.0})
    svc.calculate_lab_severity(1)
    assert repo["created"] == []


def test_calc_um_md(repo, monkeypatch):
    _exames(monkeypatch, {"ALB": 3.0})
    svc.calculate_lab_severity(1)
    assert len(repo["created"]) == 1
    assert repo["created"][0].severidade == "md"


def test_calc_dois_al(repo, monkeypatch):
    _exames(monkeypatch, {"ALB": 3.0, "HB": 10.0})
    svc.calculate_lab_severity(1)
    assert {a.severidade for a in repo["created"]} == {"al"}


def test_calc_tres_cr(repo, monkeypatch):
    _exames(monkeypatch, {"ALB": 3.0, "HB": 10.0, "K": 2.0})
    svc.calculate_lab_severity(1)
    assert {a.severidade for a in repo["created"]} == {"cr"}


def test_calc_fosforo_ne_npt_pos_npo_cr(repo, monkeypatch):
    repo["ne_npt"] = True
    _exames(monkeypatch, {"P": 1.0})
    svc.calculate_lab_severity(1)
    assert repo["created"][0].severidade == "cr"
    assert repo["created"][0].descricao == "Fosforo"


def test_calc_normaliza_desativa(repo, monkeypatch):
    existente = FakeAlert("Albumina", "md", True)
    repo["active"].append(existente)
    _exames(monkeypatch, {"ALB": 4.0})
    svc.calculate_lab_severity(1)
    assert existente.ativo is False
    assert repo["created"] == []


def test_calc_downgrade_cr_para_al(repo, monkeypatch):
    repo["active"] = [
        FakeAlert("Albumina", "cr"),
        FakeAlert("Hemoglobina", "cr"),
        FakeAlert("Potassio", "cr"),
    ]
    _exames(monkeypatch, {"ALB": 3.0, "HB": 10.0, "K": 4.0})
    svc.calculate_lab_severity(1)
    potassio = next(a for a in repo["active"] if a.descricao == "Potassio")
    albumina = next(a for a in repo["active"] if a.descricao == "Albumina")
    assert potassio.ativo is False
    assert albumina.ativo is True
    assert albumina.severidade == "al"
