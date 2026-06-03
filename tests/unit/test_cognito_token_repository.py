"""Testes da guarda de tabela ausente do repositório de token Cognito (issue #88).

``db.session`` mockado — não toca banco.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock

from repository.nutritional import cognito_token_repository as repo


def test_get_valid_token_skips_when_table_missing(monkeypatch) -> None:
    monkeypatch.setattr(repo, "_is_cognito_table_ready", lambda: False)
    session = MagicMock()
    monkeypatch.setattr(repo.db, "session", session)

    assert repo.get_valid_token() is None
    session.query.assert_not_called()


def test_upsert_token_skips_when_table_missing(monkeypatch) -> None:
    monkeypatch.setattr(repo, "_is_cognito_table_ready", lambda: False)
    session = MagicMock()
    monkeypatch.setattr(repo.db, "session", session)

    repo.upsert_token("enc", datetime.now(timezone.utc), "Bearer")

    session.execute.assert_not_called()
    session.commit.assert_not_called()


def test_upsert_token_commits_when_table_ready(monkeypatch) -> None:
    monkeypatch.setattr(repo, "_is_cognito_table_ready", lambda: True)
    monkeypatch.setattr(repo, "_current_schema", lambda: "demo")
    session = MagicMock()
    monkeypatch.setattr(repo.db, "session", session)
    set_schema_calls = []
    monkeypatch.setattr(
        repo.dbSession, "setSchema", lambda s: set_schema_calls.append(s)
    )

    repo.upsert_token("enc", datetime.now(timezone.utc), "Bearer")

    session.execute.assert_called_once()
    session.commit.assert_called_once()
    assert set_schema_calls == ["demo"]
