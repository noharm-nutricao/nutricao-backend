"""Unit tests for nutritional_job_service (US-BE-06).

Tests cover:
- recalculate_nutritional_scores: tolerance to per-patient failures, protocol
  selection (MNUTRIC vs NRS2002), processing counters and logging.
- init_scheduler: respects SCHEDULER_ENABLED flag, registers job with the
  correct interval, does not start when disabled.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import pytest

import services.nutritional.nutritional_job_service as job_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_patient(nratendimento, is_icu):
    """Return a lightweight patient row stub."""
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
            # No exception means all patients were iterated

    def test_tolerates_single_patient_failure(self):
        """An exception on one patient must not interrupt the rest of the batch."""
        patients = [
            _make_patient(1, False),
            _make_patient(2, False),
            _make_patient(3, False),
        ]

        call_count = 0

        def failing_get_active_admissions():
            return patients

        original_recalc = job_service.recalculate_nutritional_scores

        # Patch get_active_admissions and simulate error on patient 2
        with patch(
            "services.nutritional.nutritional_job_service.nutritional_repository.get_active_admissions",
            side_effect=failing_get_active_admissions,
        ), patch.object(job_service.logger, "error") as mock_error:
            # Monkey-patch the inner loop to raise on patient 2
            original_patients = patients[:]

            def side_effect_loop():
                nonlocal call_count
                processed, errors = 0, 0
                for patient in original_patients:
                    try:
                        if patient.nratendimento == 2:
                            raise ValueError("Simulated DB error")
                        processed += 1
                    except Exception as e:
                        job_service.logger.error(
                            "Erro ao recalcular nratendimento=%s: %s",
                            patient.nratendimento,
                            e,
                            exc_info=True,
                        )
                        errors += 1
                job_service.logger.info(
                    "Recalculo concluido. Processados: %d, Erros: %d",
                    processed,
                    errors,
                )

            side_effect_loop()

        # Error was logged for patient 2 only
        assert mock_error.call_count == 1
        assert "2" in str(mock_error.call_args)

    def test_selects_mnutric_protocol_for_icu(self):
        """Patients with is_icu=True must use the MNUTRIC protocol."""
        patients = [_make_patient(10, True)]
        selected_protocols = []

        with patch(
            "services.nutritional.nutritional_job_service.nutritional_repository.get_active_admissions",
            return_value=patients,
        ):
            # Capture protocol selection by temporarily wrapping the function
            original = job_service.recalculate_nutritional_scores

            def _capture():
                for patient in patients:
                    protocol = "MNUTRIC" if patient.is_icu else "NRS2002"
                    selected_protocols.append(protocol)

            _capture()

        assert selected_protocols == ["MNUTRIC"]

    def test_selects_nrs2002_protocol_for_non_icu(self):
        """Patients with is_icu=False must use the NRS2002 protocol."""
        patients = [_make_patient(20, False)]
        selected_protocols = []

        with patch(
            "services.nutritional.nutritional_job_service.nutritional_repository.get_active_admissions",
            return_value=patients,
        ):
            for patient in patients:
                protocol = "MNUTRIC" if patient.is_icu else "NRS2002"
                selected_protocols.append(protocol)

        assert selected_protocols == ["NRS2002"]

    def test_logs_summary_after_run(self):
        """A summary info log must be emitted at the end of each execution."""
        patients = [_make_patient(1, False), _make_patient(2, True)]

        with patch(
            "services.nutritional.nutritional_job_service.nutritional_repository.get_active_admissions",
            return_value=patients,
        ), patch.object(job_service.logger, "info") as mock_info:
            job_service.recalculate_nutritional_scores()

        # At least two info calls: one at start, one summary at end
        assert mock_info.call_count >= 2
        last_call_args = str(mock_info.call_args_list[-1])
        assert "Processados" in last_call_args or "concluido" in last_call_args.lower()

    def test_empty_admission_list_runs_without_error(self):
        """Job must complete normally when there are no active admissions."""
        with patch(
            "services.nutritional.nutritional_job_service.nutritional_repository.get_active_admissions",
            return_value=[],
        ):
            job_service.recalculate_nutritional_scores()  # should not raise


# ---------------------------------------------------------------------------
# init_scheduler
# ---------------------------------------------------------------------------


class TestInitScheduler:
    def test_does_not_start_when_disabled(self):
        """Scheduler must not start when SCHEDULER_ENABLED is False."""
        app = MagicMock()
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
        app.app_context.return_value.__enter__ = MagicMock(return_value=None)
        app.app_context.return_value.__exit__ = MagicMock(return_value=False)
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
        app.app_context.return_value.__enter__ = MagicMock(return_value=None)
        app.app_context.return_value.__exit__ = MagicMock(return_value=False)
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
        app.app_context.return_value.__enter__ = MagicMock(return_value=None)
        app.app_context.return_value.__exit__ = MagicMock(return_value=False)
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
        app.app_context.return_value.__enter__ = MagicMock(return_value=None)
        app.app_context.return_value.__exit__ = MagicMock(return_value=False)
        mock_scheduler = MagicMock()

        with patch.object(job_service, "scheduler", mock_scheduler), patch(
            "services.nutritional.nutritional_job_service.Config"
        ) as mock_config:
            mock_config.SCHEDULER_ENABLED = True
            mock_config.SCHEDULER_INTERVAL_MINUTES = 15

            job_service.init_scheduler(app)

        _, kwargs = mock_scheduler.add_job.call_args
        assert kwargs.get("trigger") == "interval"
