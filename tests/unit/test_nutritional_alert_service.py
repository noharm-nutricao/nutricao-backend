from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from services.nutritional import nutritional_alert_service as service


def _alerta(
    id,
    tipo,
    descricao,
    severidade,
    ativo=True,
    reconhecido=False,
    reconhecido_por=None,
    reconhecido_at=None,
    created_at=None,
):
    return SimpleNamespace(
        id=id,
        tipo=tipo,
        descricao=descricao,
        severidade=severidade,
        ativo=ativo,
        reconhecido=reconhecido,
        reconhecido_por=reconhecido_por,
        reconhecido_at=reconhecido_at,
        created_at=created_at,
    )


@patch("services.nutritional.nutritional_alert_service.nutritional_repository")
def test_get_alerts_mapeia_contrato_completo(mock_repo):
    mock_repo.get_alertas.return_value = [
        _alerta(
            1,
            "clin",
            "Baixa ingestao",
            "md",
            created_at=datetime(2026, 5, 20, 8, 14, 0),
        )
    ]
    result = service.get_alerts.__wrapped__(9999)
    assert result == [
        {
            "id": 1,
            "t": "clin",
            "sev": "md",
            "d": "Baixa ingestao",
            "al_ok": False,
            "reconhecido_at": None,
            "created_at": "2026-05-20T08:14:00",
        }
    ]
    mock_repo.get_alertas.assert_called_once_with(9999)


@patch("services.nutritional.nutritional_alert_service.nutritional_repository")
def test_get_alerts_lista_vazia(mock_repo):
    mock_repo.get_alertas.return_value = []
    assert service.get_alerts.__wrapped__(9999) == []


@patch("services.nutritional.nutritional_alert_service.nutritional_repository")
def test_get_alerts_sev_gravada(mock_repo):
    mock_repo.get_alertas.return_value = [
        _alerta(1, "lab", "Albumina", "al"),
        _alerta(2, "lab", "Fosforo", "al"),
    ]
    result = service.get_alerts.__wrapped__(9999)
    assert {r["sev"] for r in result} == {"al"}


@patch("services.nutritional.nutritional_alert_service.nutritional_repository")
def test_get_alerts_reconhecido_at_isoformat(mock_repo):
    mock_repo.get_alertas.return_value = [
        _alerta(
            5,
            "lab",
            "Magnesio",
            "cr",
            reconhecido=True,
            reconhecido_por=7,
            reconhecido_at=datetime(2026, 4, 10, 12, 0, 0),
        )
    ]
    result = service.get_alerts.__wrapped__(9999)
    assert result[0]["al_ok"] is True
    assert result[0]["reconhecido_at"] == "2026-04-10T12:00:00"
    assert result[0]["sev"] == "cr"


@pytest.mark.parametrize(
    "exception",
    [Exception("generica"), ConnectionError("conexao"), ValueError("invalido")],
)
@patch("services.nutritional.nutritional_alert_service.nutritional_repository")
def test_get_alerts_propaga_excecao(mock_repo, exception):
    mock_repo.get_alertas.side_effect = exception
    with pytest.raises(type(exception)):
        service.get_alerts.__wrapped__(9999)
