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
