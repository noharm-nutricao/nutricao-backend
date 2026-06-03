"""Testes do cliente do worker LLM (issue #88).

HTTP session mockada — não toca rede.
"""

import json
from unittest.mock import MagicMock

import pytest
import requests

from exception.validation_error import ValidationError
from services.nutritional import llm_worker_client as client
from services.nutritional.nutritional_llm_hash import LlmSummaryHashInput
from utils import status


def _hash_input(report_type: str = "resumo_clinico") -> LlmSummaryHashInput:
    return LlmSummaryHashInput(
        nratendimento=1,
        report_type=report_type,
        max_assessments=5,
        prompt_version=report_type,
        model="ANTHROPIC",
        max_tokens=800,
        context={"age": 68, "gender": "M"},
    )


def test_build_prompt_injects_context_json() -> None:
    prompt = client.build_prompt(_hash_input())

    assert client._CONTEXT_PLACEHOLDER not in prompt  # marcador foi substituído
    expected_json = json.dumps(
        {"age": 68, "gender": "M"}, ensure_ascii=False, sort_keys=True
    )
    assert expected_json in prompt


def test_build_prompt_unknown_report_type_raises_400() -> None:
    with pytest.raises(ValidationError) as exc:
        client.build_prompt(_hash_input(report_type="inexistente"))
    assert exc.value.httpStatus == status.HTTP_400_BAD_REQUEST


def test_call_llm_returns_response_field(monkeypatch) -> None:
    resp = MagicMock(status_code=status.HTTP_200_OK)
    resp.json.return_value = {"response": "Resumo clínico."}
    session = MagicMock()
    session.post.return_value = resp
    monkeypatch.setattr(client, "session", session)

    out = client.call_llm("ANTHROPIC", "PROMPT", "tok")
    assert out == "Resumo clínico."


def test_call_llm_sends_expected_request(monkeypatch) -> None:
    """Garante params=model, Bearer token e body {message: prompt}."""
    resp = MagicMock(status_code=status.HTTP_200_OK)
    resp.json.return_value = {"response": "ok"}
    session = MagicMock()
    session.post.return_value = resp
    monkeypatch.setattr(client, "session", session)

    client.call_llm("GPT", "PROMPT", "tok-123")

    _, kwargs = session.post.call_args
    assert kwargs["params"] == {"model": "GPT"}
    assert kwargs["headers"]["Authorization"] == "Bearer tok-123"
    assert kwargs["json"] == {"message": "PROMPT"}


def test_call_llm_request_exception_maps_to_502(monkeypatch) -> None:
    """Erro de rede não-Timeout (ex.: ConnectionError) → 502."""
    session = MagicMock()
    session.post.side_effect = requests.exceptions.ConnectionError("dns")
    monkeypatch.setattr(client, "session", session)

    with pytest.raises(ValidationError) as exc:
        client.call_llm("ANTHROPIC", "PROMPT", "tok")
    assert exc.value.httpStatus == status.HTTP_502_BAD_GATEWAY


def test_call_llm_200_with_invalid_json_maps_to_502(monkeypatch) -> None:
    """200 mas corpo não-JSON → 502."""
    resp = MagicMock(status_code=status.HTTP_200_OK)
    resp.json.side_effect = requests.exceptions.JSONDecodeError("bad", "doc", 0)
    session = MagicMock()
    session.post.return_value = resp
    monkeypatch.setattr(client, "session", session)

    with pytest.raises(ValidationError) as exc:
        client.call_llm("ANTHROPIC", "PROMPT", "tok")
    assert exc.value.httpStatus == status.HTTP_502_BAD_GATEWAY


def test_call_llm_200_missing_response_field_maps_to_502(monkeypatch) -> None:
    """200 mas sem o campo 'response' → 502."""
    resp = MagicMock(status_code=status.HTTP_200_OK)
    resp.json.return_value = {"foo": "bar"}
    session = MagicMock()
    session.post.return_value = resp
    monkeypatch.setattr(client, "session", session)

    with pytest.raises(ValidationError) as exc:
        client.call_llm("ANTHROPIC", "PROMPT", "tok")
    assert exc.value.httpStatus == status.HTTP_502_BAD_GATEWAY


def test_call_llm_200_non_string_response_maps_to_502(monkeypatch) -> None:
    """200 mas 'response' não-string (ex.: dict) → 502."""
    resp = MagicMock(status_code=status.HTTP_200_OK)
    resp.json.return_value = {"response": {"nested": "x"}}
    session = MagicMock()
    session.post.return_value = resp
    monkeypatch.setattr(client, "session", session)

    with pytest.raises(ValidationError) as exc:
        client.call_llm("ANTHROPIC", "PROMPT", "tok")
    assert exc.value.httpStatus == status.HTTP_502_BAD_GATEWAY


def test_call_llm_504_maps_to_504(monkeypatch) -> None:
    session = MagicMock()
    session.post.return_value = MagicMock(status_code=504, text="timeout")
    monkeypatch.setattr(client, "session", session)

    with pytest.raises(ValidationError) as exc:
        client.call_llm("ANTHROPIC", "PROMPT", "tok")
    assert exc.value.httpStatus == status.HTTP_504_GATEWAY_TIMEOUT


def test_call_llm_timeout_maps_to_504(monkeypatch) -> None:
    session = MagicMock()
    session.post.side_effect = requests.exceptions.Timeout("boom")
    monkeypatch.setattr(client, "session", session)

    with pytest.raises(ValidationError) as exc:
        client.call_llm("ANTHROPIC", "PROMPT", "tok")
    assert exc.value.httpStatus == status.HTTP_504_GATEWAY_TIMEOUT


def test_call_llm_502_maps_to_502(monkeypatch) -> None:
    session = MagicMock()
    session.post.return_value = MagicMock(status_code=502, text="bad")
    monkeypatch.setattr(client, "session", session)

    with pytest.raises(ValidationError) as exc:
        client.call_llm("ANTHROPIC", "PROMPT", "tok")
    assert exc.value.httpStatus == status.HTTP_502_BAD_GATEWAY
