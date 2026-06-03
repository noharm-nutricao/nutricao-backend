"""Testes da rota síncrona de resumo LLM (issue #88).

Exercita o corpo da view (parse do JSON → DTO → chamada ao serviço) sem passar pelo
``@api_endpoint`` (JWT/DB). Usa a função original via ``__wrapped__`` e um request context
do Flask para que ``request.get_json`` funcione. O serviço é mockado.
"""

from types import SimpleNamespace

from mobile import app
from models.requests.nutritional_llm_request import (
    LlmModel,
    NutritionalLlmSummaryRequest,
    ReportType,
)
from routes.nutritional import nutritional_llm as route

# Função original (sem o wrapper @api_endpoint), exposta por functools.wraps.
_view = route.generate_llm_summary_synchronous.__wrapped__


def test_route_parses_body_and_calls_service(monkeypatch) -> None:
    captured: dict = {}
    monkeypatch.setattr(
        route.nutritional_llm_synchronous_service,
        "generate_summary",
        lambda **kw: captured.update(kw) or {"summary": "ok"},
    )
    user = SimpleNamespace(schema="demo")

    body = {
        "report_type": "resumo_clinico",
        "max_assessments": 3,
        "model": "GPT",
        "max_tokens": 500,
    }
    with app.test_request_context(json=body):
        result = _view(nratendimento=123, user_context=user)

    assert result == {"summary": "ok"}
    assert captured["nratendimento"] == 123
    assert captured["user_context"] is user
    payload = captured["request_data"]
    assert isinstance(payload, NutritionalLlmSummaryRequest)
    assert payload.report_type == ReportType.RESUMO_CLINICO
    assert payload.max_assessments == 3
    assert payload.model == LlmModel.GPT
    assert payload.max_tokens == 500


def test_route_uses_defaults_when_body_empty(monkeypatch) -> None:
    """Sem corpo (request.get_json(silent=True) → None → {}), aplica defaults do DTO."""
    captured: dict = {}
    monkeypatch.setattr(
        route.nutritional_llm_synchronous_service,
        "generate_summary",
        lambda **kw: captured.update(kw) or {"summary": "ok"},
    )
    user = SimpleNamespace(schema="demo")

    with app.test_request_context():  # sem json → corpo vazio
        _view(nratendimento=7, user_context=user)

    payload = captured["request_data"]
    assert payload.report_type == ReportType.RESUMO_CLINICO
    assert payload.max_assessments == 5
    assert payload.model == LlmModel.ANTHROPIC
    assert payload.max_tokens == 800
