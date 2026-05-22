"""Unit tests for nutritional_repository (uncovered paths)."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from repository.nutritional import nutritional_repository as repo


# ---------------------------------------------------------------------------
# save_manual_mnutric: table-not-ready guard
# ---------------------------------------------------------------------------


def test_save_manual_mnutric_returns_none_when_table_not_ready():
    with patch.object(repo, "_is_nutritional_screening_table_ready", return_value=False):
        result = repo.save_manual_mnutric(admission_number=1, mnutric={})

    assert result is None


# ---------------------------------------------------------------------------
# update_mnutric_scores: table-not-ready guard
# ---------------------------------------------------------------------------


def test_update_mnutric_scores_returns_none_when_table_not_ready():
    with patch.object(repo, "_is_nutritional_screening_table_ready", return_value=False):
        result = repo.update_mnutric_scores(admission_number=1, mnutric={})

    assert result is None


# ---------------------------------------------------------------------------
# get_active_admissions
# ---------------------------------------------------------------------------


def test_get_active_admissions_sets_schema_and_returns_rows(monkeypatch):
    mock_session = MagicMock()
    rows = [MagicMock(nratendimento=1, is_icu=False)]
    mock_result = MagicMock()
    mock_result.fetchall.return_value = rows
    mock_session.execute.return_value = mock_result
    monkeypatch.setattr(repo.db, "session", mock_session)

    result = repo.get_active_admissions("demo")

    assert result is rows
    assert mock_session.execute.call_count == 2


# ---------------------------------------------------------------------------
# create_assessment
# ---------------------------------------------------------------------------


def test_create_assessment_adds_and_flushes(monkeypatch):
    mock_session = MagicMock()
    monkeypatch.setattr(repo.db, "session", mock_session)
    assessment = MagicMock()

    repo.create_assessment(assessment)

    mock_session.add.assert_called_once_with(assessment)
    mock_session.flush.assert_called_once()


# ---------------------------------------------------------------------------
# get_assessments_by_nratendimento
# ---------------------------------------------------------------------------


def test_get_assessments_returns_count_and_ordered_list(monkeypatch):
    count_query = MagicMock()
    count_query.filter.return_value = count_query
    count_query.count.return_value = 3

    select_query = MagicMock()
    select_query.filter.return_value = select_query
    select_query.order_by.return_value = select_query
    select_query.limit.return_value = select_query
    rows = [MagicMock(), MagicMock()]
    select_query.all.return_value = rows

    mock_session = MagicMock()
    mock_session.query.side_effect = [count_query, select_query]
    monkeypatch.setattr(repo.db, "session", mock_session)

    total, assessments = repo.get_assessments_by_nratendimento(nratendimento=42, limit=5)

    assert total == 3
    assert assessments == rows
    select_query.limit.assert_called_once_with(5)


# ---------------------------------------------------------------------------
# create_d7
# ---------------------------------------------------------------------------


def test_create_d7_creates_with_correct_fields(monkeypatch):
    mock_session = MagicMock()
    monkeypatch.setattr(repo.db, "session", mock_session)

    dt = datetime(2026, 6, 1)
    repo.create_d7(nratendimento=100, dt_prevista=dt, idusuario=5)

    mock_session.add.assert_called_once()
    mock_session.flush.assert_called_once()

    added = mock_session.add.call_args.args[0]
    assert added.nratendimento == 100
    assert added.dt_prevista == dt
    assert added.idusuario == 5
    assert added.concluido is False


def test_create_d7_without_idusuario(monkeypatch):
    mock_session = MagicMock()
    monkeypatch.setattr(repo.db, "session", mock_session)

    repo.create_d7(nratendimento=200, dt_prevista=datetime(2026, 7, 1))

    added = mock_session.add.call_args.args[0]
    assert added.idusuario is None


# ---------------------------------------------------------------------------
# get_alertas
# ---------------------------------------------------------------------------


def test_get_alertas_filters_by_nratendimento_and_ativo(monkeypatch):
    alert_query = MagicMock()
    alert_query.filter.return_value = alert_query
    rows = [MagicMock(), MagicMock()]
    alert_query.all.return_value = rows

    mock_session = MagicMock()
    mock_session.query.return_value = alert_query
    monkeypatch.setattr(repo.db, "session", mock_session)

    result = repo.get_alertas(nratendimento=99)

    assert result == rows
    alert_query.filter.assert_called_once()
    alert_query.all.assert_called_once()
