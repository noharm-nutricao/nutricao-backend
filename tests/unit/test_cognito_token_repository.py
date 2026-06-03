"""Testes do repositório de token Cognito (issue #88).

``db.session`` mockado — não toca banco. Cobrem: a guarda de tabela ausente
(``_is_cognito_table_ready``), a leitura do schema corrente (``_current_schema``),
a consulta do token válido e o UPSERT com commit imediato + re-set do schema.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock

from repository.nutritional import cognito_token_repository as repo


# --- _current_schema ----------------------------------------------------------


def test_current_schema_reads_translate_map(monkeypatch) -> None:
    connection = MagicMock()
    connection.get_execution_options.return_value = {
        "schema_translate_map": {None: "hospital_x"}
    }
    session = MagicMock()
    session.connection.return_value = connection
    monkeypatch.setattr(repo.db, "session", session)

    assert repo._current_schema() == "hospital_x"


def test_current_schema_defaults_to_demo_when_absent(monkeypatch) -> None:
    connection = MagicMock()
    connection.get_execution_options.return_value = {}
    session = MagicMock()
    session.connection.return_value = connection
    monkeypatch.setattr(repo.db, "session", session)

    assert repo._current_schema() == "demo"


def test_current_schema_defaults_to_demo_when_none_key_missing(monkeypatch) -> None:
    connection = MagicMock()
    connection.get_execution_options.return_value = {
        "schema_translate_map": {"other": "x"}
    }
    session = MagicMock()
    session.connection.return_value = connection
    monkeypatch.setattr(repo.db, "session", session)

    assert repo._current_schema() == "demo"


# --- _is_cognito_table_ready --------------------------------------------------


def test_is_cognito_table_ready_true(monkeypatch) -> None:
    session = MagicMock()
    session.execute.return_value.scalar.return_value = True
    monkeypatch.setattr(repo.db, "session", session)

    assert repo._is_cognito_table_ready() is True
    session.execute.assert_called_once()


def test_is_cognito_table_ready_false(monkeypatch) -> None:
    session = MagicMock()
    session.execute.return_value.scalar.return_value = False
    monkeypatch.setattr(repo.db, "session", session)

    assert repo._is_cognito_table_ready() is False


# --- get_valid_token ----------------------------------------------------------


def test_get_valid_token_skips_when_table_missing(monkeypatch) -> None:
    monkeypatch.setattr(repo, "_is_cognito_table_ready", lambda: False)
    session = MagicMock()
    monkeypatch.setattr(repo.db, "session", session)

    assert repo.get_valid_token() is None
    session.query.assert_not_called()


def test_get_valid_token_queries_when_table_ready(monkeypatch) -> None:
    monkeypatch.setattr(repo, "_is_cognito_table_ready", lambda: True)
    sentinel = object()
    session = MagicMock()
    session.query.return_value.filter.return_value.first.return_value = sentinel
    monkeypatch.setattr(repo.db, "session", session)

    assert repo.get_valid_token() is sentinel
    session.query.assert_called_once_with(repo.CognitoTokenCache)


def test_get_valid_token_returns_none_when_no_valid_row(monkeypatch) -> None:
    monkeypatch.setattr(repo, "_is_cognito_table_ready", lambda: True)
    session = MagicMock()
    session.query.return_value.filter.return_value.first.return_value = None
    monkeypatch.setattr(repo.db, "session", session)

    assert repo.get_valid_token() is None


# --- upsert_token -------------------------------------------------------------


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


def test_upsert_token_uses_default_token_type(monkeypatch) -> None:
    """token_type tem default 'Bearer' — chamável sem o 3º argumento."""
    monkeypatch.setattr(repo, "_is_cognito_table_ready", lambda: True)
    monkeypatch.setattr(repo, "_current_schema", lambda: "demo")
    session = MagicMock()
    monkeypatch.setattr(repo.db, "session", session)
    monkeypatch.setattr(repo.dbSession, "setSchema", lambda s: None)

    repo.upsert_token("enc", datetime.now(timezone.utc))

    session.execute.assert_called_once()
    session.commit.assert_called_once()


def test_upsert_token_reapplies_schema_after_commit(monkeypatch) -> None:
    """O schema é re-aplicado DEPOIS do commit (perdido no commit)."""
    monkeypatch.setattr(repo, "_is_cognito_table_ready", lambda: True)
    monkeypatch.setattr(repo, "_current_schema", lambda: "tenant_y")
    order: list = []
    session = MagicMock()
    session.commit.side_effect = lambda: order.append("commit")
    monkeypatch.setattr(repo.db, "session", session)
    monkeypatch.setattr(
        repo.dbSession, "setSchema", lambda s: order.append(f"setSchema:{s}")
    )

    repo.upsert_token("enc", datetime.now(timezone.utc))

    assert order == ["commit", "setSchema:tenant_y"]
