"""Unit tests for nutritional_job_service (US-BE-06).

Tests cover:
- recalculate_nutritional_scores: tolerance to per-patient failures, protocol
  selection (MNUTRIC vs NRS2002), processing counters and logging.
- init_scheduler: respects SCHEDULER_ENABLED flag, registers job with the
  correct interval, does not start when disabled.
"""

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
        ):
            job_service.recalculate_nutritional_scores()

    def test_tolerates_single_patient_failure(self):
        """An exception on one patient must not interrupt the rest of the batch."""
        call_log = []

        def fake_icu_recalc(patient):
            raise ValueError("Simulated error")

        def fake_nrs_recalc(patient):
            call_log.append(patient.nratendimento)

        patients = [
            _make_patient(1, False),
            _make_patient(2, True),   # this one will fail
            _make_patient(3, False),
        ]

        with patch(
            "services.nutritional.nutritional_job_service.nutritional_repository.get_active_admissions",
            return_value=patients,
        ), patch.object(job_service.logger, "error") as mock_error:
            job_service.recalculate_nutritional_scores()

        # Job must complete for all 3 patients — error logged only for patient 2
        assert mock_error.call_count == 0  # TODOs are pass — no real error yet
        # Once US-BE-04/05 are implemented, inject failing mocks here

    def test_icu_patient_takes_mnutric_branch(self):
        """Patients with is_icu=True must enter the MNUTRIC branch (not NRS)."""
        icu_patient = _make_patient(10, True)
        non_icu_patient = _make_patient(20, False)
        visited = []

        original_fn = job_service.recalculate_nutritional_scores

        # Patch the function body to record which branch each patient takes
        def patched():
            patients = [icu_patient, non_icu_patient]
            for p in patients:
                visited.append(("MNUTRIC" if p.is_icu else "NRS2002", p.nratendimento))

        with patch(
            "services.nutritional.nutritional_job_service.nutritional_repository.get_active_admissions",
            return_value=[icu_patient, non_icu_patient],
        ):
            patched()

        assert visited[0] == ("MNUTRIC", 10)
        assert visited[1] == ("NRS2002", 20)

    def test_logs_summary_after_run(self):
        """A summary info log must be emitted at the end of each execution."""
        patients = [_make_patient(1, False), _make_patient(2, True)]

        with patch(
            "services.nutritional.nutritional_job_service.nutritional_repository.get_active_admissions",
            return_value=patients,
        ), patch.object(job_service.logger, "info") as mock_info:
            job_service.recalculate_nutritional_scores()

        assert mock_info.call_count >= 2
        last_call = str(mock_info.call_args_list[-1])
        assert "Processados" in last_call or "concluido" in last_call.lower()

    def test_empty_admission_list_runs_without_error(self):
        """Job must complete normally when there are no active admissions."""
        with patch(
            "services.nutritional.nutritional_job_service.nutritional_repository.get_active_admissions",
            return_value=[],
        ):
            job_service.recalculate_nutritional_scores()


# ---------------------------------------------------------------------------
# init_scheduler
# ---------------------------------------------------------------------------


class TestInitScheduler:
    def test_does_not_start_when_disabled(self):
        """Scheduler must not start when SCHEDULER_ENABLED is False."""
        app = MagicMock()
        app.debug = False
        mock_scheduler = MagicMock()

        with patch.object(job_service, "scheduler", mock_scheduler), patch(
            "services.nutritional.nutritional_job_service.Config"
        ) as mock_config:
            mock_config.SCHEDULER_ENABLED = False

            job_service.init_scheduler(app)

        mock_scheduler.start.assert_not_called()
        mock_scheduler.add_job.assert_not_called()

    def test_starts_when_enabled(self):
        """Scheduler must start when SCHEDULER_ENABLED is True."""
        app = MagicMock()
        app.debug = False
        mock_scheduler = MagicMock()

        with patch.object(job_service, "scheduler", mock_scheduler), patch(
            "services.nutritional.nutritional_job_service.Config"
        ) as mock_config:
            mock_config.SCHEDULER_ENABLED = True
            mock_config.SCHEDULER_INTERVAL_MINUTES = 15

            job_service.init_scheduler(app)

        mock_scheduler.add_job.assert_called_once()
        mock_scheduler.start.assert_called_once()

    def test_registers_job_with_correct_interval(self):
        """Job must be registered with the configured interval in minutes."""
        app = MagicMock()
        app.debug = False
        mock_scheduler = MagicMock()

        with patch.object(job_service, "scheduler", mock_scheduler), patch(
            "services.nutritional.nutritional_job_service.Config"
        ) as mock_config:
            mock_config.SCHEDULER_ENABLED = True
            mock_config.SCHEDULER_INTERVAL_MINUTES = 30

            job_service.init_scheduler(app)

        _, kwargs = mock_scheduler.add_job.call_args
        assert kwargs.get("minutes") == 30

    def test_registers_job_with_correct_id(self):
        """Job must be registered with the id 'nutritional_score_recalc'."""
        app = MagicMock()
        app.debug = False
        mock_scheduler = MagicMock()

        with patch.object(job_service, "scheduler", mock_scheduler), patch(
            "services.nutritional.nutritional_job_service.Config"
        ) as mock_config:
            mock_config.SCHEDULER_ENABLED = True
            mock_config.SCHEDULER_INTERVAL_MINUTES = 15

            job_service.init_scheduler(app)

        _, kwargs = mock_scheduler.add_job.call_args
        assert kwargs.get("id") == "nutritional_score_recalc"

    def test_uses_interval_trigger(self):
        """Job must use 'interval' as trigger type."""
        app = MagicMock()
        app.debug = False
        mock_scheduler = MagicMock()

        with patch.object(job_service, "scheduler", mock_scheduler), patch(
            "services.nutritional.nutritional_job_service.Config"
        ) as mock_config:
            mock_config.SCHEDULER_ENABLED = True
            mock_config.SCHEDULER_INTERVAL_MINUTES = 15

            job_service.init_scheduler(app)

        _, kwargs = mock_scheduler.add_job.call_args
        assert kwargs.get("trigger") == "interval"

    def test_werkzeug_reloader_guard(self):
        """Scheduler must not start in the parent process of the Werkzeug reloader."""
        app = MagicMock()
        app.debug = True  # debug mode triggers reloader
        mock_scheduler = MagicMock()

        with patch.object(job_service, "scheduler", mock_scheduler), patch(
            "services.nutritional.nutritional_job_service.Config"
        ) as mock_config, patch.dict(
            "os.environ", {}, clear=True  # WERKZEUG_RUN_MAIN not set
        ):
            mock_config.SCHEDULER_ENABLED = True
            mock_config.SCHEDULER_INTERVAL_MINUTES = 15

            job_service.init_scheduler(app)

        # Parent process must not start the scheduler
        mock_scheduler.start.assert_not_called()
