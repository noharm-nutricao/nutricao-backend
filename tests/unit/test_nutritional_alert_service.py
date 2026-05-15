"""Unit tests: nutritional_alert_service."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from services.nutritional import nutritional_alert_service as service


def _alerta(id, tipo, descricao, severidade, reconhecido=False, reconhecido_at=None):
    return SimpleNamespace(
        id=id,
        tipo=tipo,
        descricao=descricao,
        severidade=severidade,
        reconhecido=reconhecido,
        reconhecido_at=reconhecido_at,
    )


@pytest.mark.parametrize(
    "alertas, expected",
    [
        pytest.param(
            [
                _alerta(1, "nutricional", "Risco de desnutrição", "alta"),
                _alerta(2, "hidrico", "Déficit hídrico", "media"),
            ],
            [
                {"id": 1, "tipo": "nutricional", "descricao": "Risco de desnutrição", "severidade": "alta", "reconhecido": False, "reconhecido_at": None},
                {"id": 2, "tipo": "hidrico", "descricao": "Déficit hídrico", "severidade": "media", "reconhecido": False, "reconhecido_at": None},
            ],
            id="retorna-lista-com-alertas",
        ),
        pytest.param([], [], id="retorna-lista-vazia"),
        pytest.param(
            [_alerta(3, "nutricional", "Alerta reconhecido", "baixa", reconhecido=True)],
            [{"id": 3, "tipo": "nutricional", "descricao": "Alerta reconhecido", "severidade": "baixa", "reconhecido": True, "reconhecido_at": None}],
            id="reconhecido-sem-data",
        ),
    ],
)
@patch("services.nutritional.nutritional_alert_service.nutritional_repository")
def test_get_alertas_caminho_feliz(mock_repo, alertas, expected):
    """get_alertas: retorna lista de alertas corretamente mapeada"""
    mock_repo.get_alertas.return_value = alertas
    result = service.get_alerts.__wrapped__(9999)
    assert result == expected
    mock_repo.get_alertas.assert_called_once_with(9999)


@pytest.mark.parametrize(
    "alertas, expected",
    [
        pytest.param(
            [_alerta(4, "nutricional", "Alerta", "alta", reconhecido=None)],
            [{"id": 4, "tipo": "nutricional", "descricao": "Alerta", "severidade": "alta", "reconhecido": False, "reconhecido_at": None}],
            id="reconhecido-none-vira-false",
        ),
        pytest.param(
            [_alerta(5, "nutricional", "Alerta com data", "media", reconhecido=True, reconhecido_at=datetime(2026, 4, 10, 12, 0, 0))],
            [{"id": 5, "tipo": "nutricional", "descricao": "Alerta com data", "severidade": "media", "reconhecido": True, "reconhecido_at": "2026-04-10T12:00:00"}],
            id="reconhecido-com-data-isoformat",
        ),
        pytest.param(
            [_alerta(6, "nutricional", "Alerta", "alta")] * 100,
            100,
            id="retorna-100-alertas",
            ),
    ],
)
@patch("services.nutritional.nutritional_alert_service.nutritional_repository")
def test_get_alertas_caminho_do_meio(mock_repo, alertas, expected):
    """get_alertas: comportamentos intermediários"""
    mock_repo.get_alertas.return_value = alertas
    result = service.get_alerts.__wrapped__(9999)
    if isinstance(expected, int):
        assert len(result) == expected
    else:
        assert result == expected


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(Exception("Erro genérico"), id="excecao-generica"),
        pytest.param(ConnectionError("Falha na conexão"), id="falha-conexao"),
        pytest.param(ValueError("Valor inválido"), id="valor-invalido"),
    ],
)
@patch("services.nutritional.nutritional_alert_service.nutritional_repository")
def test_get_alertas_caminho_nao_feliz(mock_repo, exception):
    """get_alertas: propaga exceção do repositório"""
    mock_repo.get_alertas.side_effect = exception
    with pytest.raises(type(exception)):
        service.get_alerts.__wrapped__(9999)