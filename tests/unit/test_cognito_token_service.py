"""Testes do serviço de token M2M do Cognito (issue #88).

Repositório e HTTP session mockados — não tocam banco nem rede.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import requests

from exception.validation_error import ValidationError
from services.nutritional import cognito_token_service as svc
from utils import status


def test_get_access_token_cache_hit(monkeypatch) -> None:
    monkeypatch.setattr(
        svc.cognito_token_repository,
        "get_valid_token",
        lambda: SimpleNamespace(access_token="enc"),
    )
    monkeypatch.setattr(svc, "decrypt_data", lambda c: "plain-token")
    session = MagicMock()
    monkeypatch.setattr(svc, "session", session)

    assert svc.get_access_token() == "plain-token"
    session.post.assert_not_called()  # HIT → não chama o Cognito


def test_get_access_token_miss_fetches_and_upserts(monkeypatch) -> None:
    monkeypatch.setattr(svc.cognito_token_repository, "get_valid_token", lambda: None)
    monkeypatch.setattr(svc, "encrypt_data", lambda t: f"enc:{t}")

    resp = MagicMock(status_code=status.HTTP_200_OK)
    resp.json.return_value = {
        "access_token": "new-token",
        "expires_in": 3600,
        "token_type": "Bearer",
    }
    session = MagicMock()
    session.post.return_value = resp
    monkeypatch.setattr(svc, "session", session)

    captured: dict = {}
    monkeypatch.setattr(
        svc.cognito_token_repository,
        "upsert_token",
        lambda enc, exp, tt: captured.update(enc=enc, exp=exp, tt=tt),
    )

    before = datetime.now(timezone.utc)
    result = svc.get_access_token()
    after = datetime.now(timezone.utc)

    assert result == "new-token"
    assert captured["enc"] == "enc:new-token"
    assert captured["tt"] == "Bearer"
    # expires_at ~ agora + 3600 - 60s (margem)
    expected = before + timedelta(seconds=3600 - 60)
    assert abs((captured["exp"] - expected).total_seconds()) <= (after - before).total_seconds() + 1


def test_get_access_token_timeout_maps_to_504(monkeypatch) -> None:
    monkeypatch.setattr(svc.cognito_token_repository, "get_valid_token", lambda: None)
    session = MagicMock()
    session.post.side_effect = requests.exceptions.Timeout("boom")
    monkeypatch.setattr(svc, "session", session)

    with pytest.raises(ValidationError) as exc:
        svc.get_access_token()
    assert exc.value.httpStatus == status.HTTP_504_GATEWAY_TIMEOUT


def test_get_access_token_non_200_maps_to_502(monkeypatch) -> None:
    monkeypatch.setattr(svc.cognito_token_repository, "get_valid_token", lambda: None)
    session = MagicMock()
    session.post.return_value = MagicMock(status_code=403, text="forbidden")
    monkeypatch.setattr(svc, "session", session)

    with pytest.raises(ValidationError) as exc:
        svc.get_access_token()
    assert exc.value.httpStatus == status.HTTP_502_BAD_GATEWAY
