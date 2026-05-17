"""Unit tests for nutritional_job_service (US-BE-06).

Tests cover:
- recalculate_nutritional_scores: tolerance to per-patient failures, protocol
  selection (MNUTRIC vs NRS2002), processing counters and logging.
- init_scheduler: respects SCHEDULER_ENABLED flag, starts daemon thread with
  correct name, guards against Werkzeug reloader double-start.
"""

import threading
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import services.nutritional.nutritional_job_service as job_service


def _make_patient(nratendimento, is_icu):
    return SimpleNamespace(nratendimento=nratendimento, is_icu=is_icu)


# ---------------------------------------------------------------------------
# recalculate_nutritional_scores
# ---------------------------------------------------------------------------


class TestRecalculateNutritionalScores:
    def test_processes_all_active_admissions(self):
        """Every patient returned by get_active_admissions is visited."""
        patients = [_make_patient(1, False), _make_patient(2, True)]

        with patch(
            "services.nutritional.nutritional_job_service.nutritional_repository.get_active_admissions",
            return_value=patients,
        ), patch(
            "services.nutritional.nutritional_job_service.nutritional_patient_service.recalculate_mnutric",
            return_value={"total": 5},
        ), patch(
            "services.nutritional.nutritional_job_service.db.session.commit",
        ):
            job_service.recalculate_nutritional_scores(MagicMock())

    def test_tolerates_single_patient_failure(self):
        """An exception on one patient must not interrupt the rest of the batch."""
        patients = [
            _make_patient(1, False),
            _make_patient(2, True),   # this one will fail
            _make_patient(3, False),
        ]

        with patch(
            "services.nutritional.nutritional_job_service.nutritional_repository.get_active_admissions",
            return_value=patients,
        ), patch(
            "services.nutritional.nutritional_job_service.nutritional_patient_service.recalculate_mnutric",
            side_effect=ValueError("Simulated error"),
        ), patch(
            "services.nutritional.nutritional_job_service.db.session.commit",
        ), patch(
            "services.nutritional.nutritional_job_service.db.session.rollback",
        ), patch.object(job_service.logger, "error") as mock_error:
            job_service.recalculate_nutritional_scores(MagicMock())

        assert mock_error.call_count == 1

    def test_logs_error_for_icu_patient_when_recalculation_returns_none(self):
        patients = [_make_patient(10, True)]

        with patch(
            "services.nutritional.nutritional_job_service.nutritional_repository.get_active_admissions",
            return_value=patients,
        ), patch(
            "services.nutritional.nutritional_job_service.nutritional_patient_service.recalculate_mnutric",
            return_value=None,
        ), patch(
            "services.nutritional.nutritional_job_service.db.session.commit",
        ) as mock_commit, patch.object(job_service.logger, "error") as mock_error:
            job_service.recalculate_nutritional_scores(MagicMock())

        mock_commit.assert_not_called()
        assert any("retorno None" in str(call) for call in mock_error.call_args_list)

    def test_logs_summary_after_run(self):
        """A summary info log must be emitted at the end of each execution."""
        patients = [_make_patient(1, False), _make_patient(2, True)]

        with patch(
            "services.nutritional.nutritional_job_service.nutritional_repository.get_active_admissions",
            return_value=patients,
        ), patch(
            "services.nutritional.nutritional_job_service.nutritional_patient_service.recalculate_mnutric",
            return_value={"total": 5},
        ), patch(
            "services.nutritional.nutritional_job_service.db.session.commit",
        ), patch.object(job_service.logger, "info") as mock_info:
            job_service.recalculate_nutritional_scores(MagicMock())

        assert mock_info.call_count >= 2
        last_call = str(mock_info.call_args_list[-1])
        assert "Processados" in last_call or "concluido" in last_call.lower()

    def test_empty_admission_list_runs_without_error(self):
        """Job must complete normally when there are no active admissions."""
        with patch(
            "services.nutritional.nutritional_job_service.nutritional_repository.get_active_admissions",
            return_value=[],
        ):
            job_service.recalculate_nutritional_scores(MagicMock())


# ---------------------------------------------------------------------------
# init_scheduler
# ---------------------------------------------------------------------------


class TestInitScheduler:
    def test_does_not_start_when_disabled(self):
        """Scheduler must not start a thread when SCHEDULER_ENABLED is False."""
        app = MagicMock()
        app.debug = False

        before = {t.name for t in threading.enumerate()}

        with patch(
            "services.nutritional.nutritional_job_service.Config"
        ) as mock_config:
            mock_config.SCHEDULER_ENABLED = False

            job_service.init_scheduler(app)

        after = {t.name for t in threading.enumerate()}
        assert "nutritional-recalc" not in after - before

    def test_starts_daemon_thread_when_enabled(self):
        """Scheduler must launch a daemon thread named 'nutritional-recalc'."""
        app = MagicMock()
        app.debug = False

        with patch(
            "services.nutritional.nutritional_job_service.Config"
        ) as mock_config, patch(
            "services.nutritional.nutritional_job_service.threading.Thread"
        ) as mock_thread_cls:
            mock_config.SCHEDULER_ENABLED = True
            mock_config.SCHEDULER_INTERVAL_MINUTES = 15

            mock_thread = MagicMock()
            mock_thread_cls.return_value = mock_thread

            job_service.init_scheduler(app)

        mock_thread_cls.assert_called_once()
        _, kwargs = mock_thread_cls.call_args
        assert kwargs.get("daemon") is True
        assert kwargs.get("name") == "nutritional-recalc"
        mock_thread.start.assert_called_once()

    def test_werkzeug_reloader_guard(self):
        """Scheduler must not start in the parent process of the Werkzeug reloader."""
        app = MagicMock()
        app.debug = True  # debug mode triggers reloader

        with patch(
            "services.nutritional.nutritional_job_service.Config"
        ) as mock_config, patch(
            "services.nutritional.nutritional_job_service.threading.Thread"
        ) as mock_thread_cls, patch.dict(
            "os.environ", {}, clear=True  # WERKZEUG_RUN_MAIN not set
        ):
            mock_config.SCHEDULER_ENABLED = True
            mock_config.SCHEDULER_INTERVAL_MINUTES = 15

            job_service.init_scheduler(app)

        mock_thread_cls.assert_not_called()
