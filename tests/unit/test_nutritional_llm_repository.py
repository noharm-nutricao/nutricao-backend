"""Testes da camada de cache do repositório LLM (issue #88).

Testes puros: ``_is_llm_resumo_table_ready`` e ``db.session`` são mockados, então não tocam
no banco. Cobrem a guarda de "tabela ausente" (trata como MISS / no-op) e o commit imediato
do insert (Opção A).
"""

from unittest.mock import MagicMock

from repository.nutritional import nutritional_llm_repository as repo


def test_get_cached_summary_skips_when_table_missing(monkeypatch) -> None:
    monkeypatch.setattr(repo, "_is_llm_resumo_table_ready", lambda: False)
    session = MagicMock()
    monkeypatch.setattr(repo.db, "session", session)

    assert repo.get_cached_summary("abc") is None
    session.query.assert_not_called()


def test_get_cached_summary_queries_when_table_ready(monkeypatch) -> None:
    monkeypatch.setattr(repo, "_is_llm_resumo_table_ready", lambda: True)
    sentinel = object()
    session = MagicMock()
    session.query.return_value.filter.return_value.first.return_value = sentinel
    monkeypatch.setattr(repo.db, "session", session)

    assert repo.get_cached_summary("abc") is sentinel
    session.query.assert_called_once()


def test_insert_pending_job_skips_when_table_missing(monkeypatch) -> None:
    monkeypatch.setattr(repo, "_is_llm_resumo_table_ready", lambda: False)
    session = MagicMock()
    monkeypatch.setattr(repo.db, "session", session)

    repo.insert_pending_job(
        context_hash="abc",
        nratendimento=1,
        report_type="resumo_clinico",
        max_assessments=5,
        prompt_version="resumo_clinico",
        model="ANTHROPIC",
    )

    session.execute.assert_not_called()
    session.commit.assert_not_called()


def test_insert_pending_job_commits_immediately_when_table_ready(monkeypatch) -> None:
    """Opção A: execute -> commit -> re-set do schema."""
    monkeypatch.setattr(repo, "_is_llm_resumo_table_ready", lambda: True)
    monkeypatch.setattr(repo, "_current_schema", lambda: "demo")
    session = MagicMock()
    monkeypatch.setattr(repo.db, "session", session)
    set_schema_calls = []
    monkeypatch.setattr(
        repo.dbSession, "setSchema", lambda schema: set_schema_calls.append(schema)
    )

    repo.insert_pending_job(
        context_hash="abc",
        nratendimento=1,
        report_type="resumo_clinico",
        max_assessments=5,
        prompt_version="resumo_clinico",
        model="ANTHROPIC",
    )

    session.execute.assert_called_once()
    session.commit.assert_called_once()
    assert set_schema_calls == ["demo"]
