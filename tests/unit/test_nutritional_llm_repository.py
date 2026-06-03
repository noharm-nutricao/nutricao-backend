"""Testes da camada de cache do repositório LLM (issue #88).

Testes puros: ``_is_llm_resumo_table_ready`` e ``db.session`` são mockados, então não tocam
no banco. Cobrem a guarda de "tabela ausente" (trata como MISS / no-op) e o commit imediato
do insert (Opção A).
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock

from repository.nutritional import nutritional_llm_repository as repo


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


def test_current_schema_defaults_to_demo(monkeypatch) -> None:
    connection = MagicMock()
    connection.get_execution_options.return_value = {}
    session = MagicMock()
    session.connection.return_value = connection
    monkeypatch.setattr(repo.db, "session", session)

    assert repo._current_schema() == "demo"


# --- _is_llm_resumo_table_ready -----------------------------------------------


def test_is_llm_resumo_table_ready_true(monkeypatch) -> None:
    monkeypatch.setattr(repo, "_current_schema", lambda: "demo")
    session = MagicMock()
    session.execute.return_value.scalar.return_value = True
    monkeypatch.setattr(repo.db, "session", session)

    assert repo._is_llm_resumo_table_ready() is True
    session.execute.assert_called_once()


def test_is_llm_resumo_table_ready_false(monkeypatch) -> None:
    monkeypatch.setattr(repo, "_current_schema", lambda: "demo")
    session = MagicMock()
    session.execute.return_value.scalar.return_value = False
    monkeypatch.setattr(repo.db, "session", session)

    assert repo._is_llm_resumo_table_ready() is False


# --- get_cached_summary -------------------------------------------------------


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


def test_insert_pending_job_sets_schema_after_commit(monkeypatch) -> None:
    """O re-set do schema acontece DEPOIS do commit (perdido no commit)."""
    monkeypatch.setattr(repo, "_is_llm_resumo_table_ready", lambda: True)
    monkeypatch.setattr(repo, "_current_schema", lambda: "tenant_z")
    order: list = []
    session = MagicMock()
    session.commit.side_effect = lambda: order.append("commit")
    monkeypatch.setattr(repo.db, "session", session)
    monkeypatch.setattr(
        repo.dbSession, "setSchema", lambda s: order.append(f"setSchema:{s}")
    )

    repo.insert_pending_job(
        context_hash="abc",
        nratendimento=1,
        report_type="resumo_clinico",
        max_assessments=5,
        prompt_version="resumo_clinico",
        model="ANTHROPIC",
    )

    assert order == ["commit", "setSchema:tenant_z"]


# --- mark_summary_done --------------------------------------------------------


def test_mark_summary_done_skips_when_table_missing(monkeypatch) -> None:
    monkeypatch.setattr(repo, "_is_llm_resumo_table_ready", lambda: False)
    session = MagicMock()
    monkeypatch.setattr(repo.db, "session", session)

    repo.mark_summary_done(
        context_hash="abc",
        summary="resumo",
        tokens_used=None,
        processed_at=datetime.now(timezone.utc),
    )

    session.query.assert_not_called()


def test_mark_summary_done_updates_without_own_commit(monkeypatch) -> None:
    """UPDATE da linha do hash, sem commit próprio (segue a transação da request)."""
    monkeypatch.setattr(repo, "_is_llm_resumo_table_ready", lambda: True)
    session = MagicMock()
    update_mock = session.query.return_value.filter.return_value.update
    monkeypatch.setattr(repo.db, "session", session)

    processed_at = datetime.now(timezone.utc)
    repo.mark_summary_done(
        context_hash="abc",
        summary="resumo gerado",
        tokens_used=412,
        processed_at=processed_at,
    )

    session.query.assert_called_once_with(repo.NutritionalLlmSummary)
    update_mock.assert_called_once()
    values = update_mock.call_args.args[0]
    assert values == {
        "status": "done",
        "summary": "resumo gerado",
        "tokens_used": 412,
        "processed_at": processed_at,
    }
    session.commit.assert_not_called()  # sem commit próprio
