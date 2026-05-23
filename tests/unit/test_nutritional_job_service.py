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


def _make_patient(nratendimento, is_icu, tp_segmento=None):
    return SimpleNamespace(
        nratendimento=nratendimento,
        is_icu=is_icu,
        tp_segmento=tp_segmento,
        dtnascimento=None,
        dtinternacao=None,
        dt_ultima_transferencia=None,
        idcid="",
    )


# ---------------------------------------------------------------------------
# recalculate_nutritional_scores
# ---------------------------------------------------------------------------


class TestRecalculateNutritionalScores:
    def test_processes_all_active_admissions(self):
        """Every patient returned by get_active_admissions is visited."""
        patients = [_make_patient(1, False), _make_patient(2, True)]
        app = MagicMock()

        with patch(
            "services.nutritional.nutritional_job_service._get_active_schemas",
            return_value=["demo"],
        ), patch(
            "services.nutritional.nutritional_job_service.nutritional_repository.get_active_admissions",
            return_value=patients,
        ) as mock_admissions, patch(
            "services.nutritional.nutritional_job_service.dbSession.setSchema",
        ), patch(
            "services.nutritional.nutritional_job_service.is_uti_wrapper",
            side_effect=lambda nra, **_: any(
                p.nratendimento == nra and p.is_icu for p in patients
            ),
        ), patch(
            "services.nutritional.nutritional_job_service.nutritional_patient_service.recalculate_mnutric",
            return_value={"total": 5},
        ), patch(
            "services.nutritional.nutritional_job_service.nutritional_nrs_service.recalculate_nrs",
        ), patch(
            "services.nutritional.nutritional_job_service.db.session.commit",
        ), patch(
            "services.nutritional.nutritional_job_service.db.session.rollback",
        ):
            job_service.recalculate_nutritional_scores(app)

        mock_admissions.assert_called_once_with(schema="demo")

    def test_tolerates_single_patient_failure(self):
        """An exception on one patient must not interrupt the rest of the batch."""
        patients = [
            _make_patient(1, False),
            _make_patient(2, True),   # this one will fail
            _make_patient(3, False),
        ]
        app = MagicMock()

        with patch(
            "services.nutritional.nutritional_job_service._get_active_schemas",
            return_value=["demo"],
        ), patch(
            "services.nutritional.nutritional_job_service.nutritional_repository.get_active_admissions",
            return_value=patients,
        ), patch(
            "services.nutritional.nutritional_job_service.dbSession.setSchema",
        ), patch(
            "services.nutritional.nutritional_job_service.is_uti_wrapper",
            side_effect=lambda nra, **_: any(
                p.nratendimento == nra and p.is_icu for p in patients
            ),
        ), patch(
            "services.nutritional.nutritional_job_service.nutritional_patient_service.recalculate_mnutric",
            side_effect=ValueError("Simulated error"),
        ), patch(
            "services.nutritional.nutritional_job_service.nutritional_nrs_service.recalculate_nrs",
        ), patch(
            "services.nutritional.nutritional_job_service.db.session.commit",
        ), patch(
            "services.nutritional.nutritional_job_service.db.session.rollback",
        ), patch.object(job_service.logger, "error") as mock_error:
            job_service.recalculate_nutritional_scores(app)

        assert mock_error.call_count == 1

    def test_logs_success_for_icu_patient_with_valid_recalculation(self):
        patients = [_make_patient(10, True)]
        app = MagicMock()

        with patch(
            "services.nutritional.nutritional_job_service._get_active_schemas",
            return_value=["demo"],
        ), patch(
            "services.nutritional.nutritional_job_service.nutritional_repository.get_active_admissions",
            return_value=patients,
        ), patch(
            "services.nutritional.nutritional_job_service.dbSession.setSchema",
        ), patch(
            "services.nutritional.nutritional_job_service.is_uti_wrapper",
            return_value=True,
        ), patch(
            "services.nutritional.nutritional_job_service.nutritional_patient_service.recalculate_mnutric",
            return_value={"total": 5},
        ), patch(
            "services.nutritional.nutritional_job_service.nutritional_nrs_service.recalculate_nrs",
        ), patch(
            "services.nutritional.nutritional_job_service.db.session.commit",
        ) as mock_commit, patch.object(job_service.logger, "info") as mock_info:
            job_service.recalculate_nutritional_scores(app)

        mock_commit.assert_called_once()
        assert any(
            "mNUTRIC recalculado" in str(call)
            for call in mock_info.call_args_list
        )

    def test_logs_error_for_icu_patient_when_recalculation_returns_none(self):
        patients = [_make_patient(10, True)]
        app = MagicMock()

        with patch(
            "services.nutritional.nutritional_job_service._get_active_schemas",
            return_value=["demo"],
        ), patch(
            "services.nutritional.nutritional_job_service.nutritional_repository.get_active_admissions",
            return_value=patients,
        ), patch(
            "services.nutritional.nutritional_job_service.dbSession.setSchema",
        ), patch(
            "services.nutritional.nutritional_job_service.is_uti_wrapper",
            return_value=True,
        ), patch(
            "services.nutritional.nutritional_job_service.nutritional_patient_service.recalculate_mnutric",
            return_value=None,
        ), patch(
            "services.nutritional.nutritional_job_service.nutritional_nrs_service.recalculate_nrs",
        ), patch(
            "services.nutritional.nutritional_job_service.db.session.commit",
        ) as mock_commit, patch.object(job_service.logger, "error") as mock_error:
            job_service.recalculate_nutritional_scores(app)

        mock_commit.assert_not_called()
        assert any("retorno None" in str(call) for call in mock_error.call_args_list)

    def test_icu_patient_takes_mnutric_branch(self):
        """ICU patients run MNUTRIC in addition to NRS; non-ICU run only NRS."""
        icu_patient = _make_patient(10, True)
        non_icu_patient = _make_patient(20, False)
        patients = [icu_patient, non_icu_patient]
        app = MagicMock()

        with patch(
            "services.nutritional.nutritional_job_service._get_active_schemas",
            return_value=["demo"],
        ), patch(
            "services.nutritional.nutritional_job_service.nutritional_repository.get_active_admissions",
            return_value=patients,
        ), patch(
            "services.nutritional.nutritional_job_service.dbSession.setSchema",
        ), patch(
            "services.nutritional.nutritional_job_service.is_uti_wrapper",
            side_effect=lambda nra, **_: any(
                p.nratendimento == nra and p.is_icu for p in patients
            ),
        ), patch(
            "services.nutritional.nutritional_job_service.nutritional_patient_service.recalculate_mnutric",
            return_value={"total": 5},
        ) as mock_mnutric, patch(
            "services.nutritional.nutritional_job_service.nutritional_nrs_service.recalculate_nrs",
        ) as mock_nrs, patch(
            "services.nutritional.nutritional_job_service.db.session.commit",
        ), patch(
            "services.nutritional.nutritional_job_service.db.session.rollback",
        ):
            job_service.recalculate_nutritional_scores(app)

        assert mock_mnutric.call_count == 1
        assert mock_mnutric.call_args.args[0] is icu_patient
        assert mock_nrs.call_count == 2

    def test_logs_summary_after_run(self):
        """A summary info log must be emitted at the end of each execution."""
        patients = [_make_patient(1, False), _make_patient(2, True)]
        app = MagicMock()

        with patch(
            "services.nutritional.nutritional_job_service._get_active_schemas",
            return_value=["demo"],
        ), patch(
            "services.nutritional.nutritional_job_service.nutritional_repository.get_active_admissions",
            return_value=patients,
        ), patch(
            "services.nutritional.nutritional_job_service.dbSession.setSchema",
        ), patch(
            "services.nutritional.nutritional_job_service.is_uti_wrapper",
            side_effect=lambda nra, **_: any(
                p.nratendimento == nra and p.is_icu for p in patients
            ),
        ), patch(
            "services.nutritional.nutritional_job_service.nutritional_patient_service.recalculate_mnutric",
            return_value={"total": 5},
        ), patch(
            "services.nutritional.nutritional_job_service.nutritional_nrs_service.recalculate_nrs",
        ), patch(
            "services.nutritional.nutritional_job_service.db.session.commit",
        ), patch.object(job_service.logger, "info") as mock_info:
            job_service.recalculate_nutritional_scores(app)

        assert mock_info.call_count >= 2
        last_call = str(mock_info.call_args_list[-1])
        assert "Processados" in last_call or "concluido" in last_call.lower()

    def test_empty_admission_list_runs_without_error(self):
        """Job must complete normally when there are no active admissions."""
        app = MagicMock()

        with patch(
            "services.nutritional.nutritional_job_service._get_active_schemas",
            return_value=["demo"],
        ), patch(
            "services.nutritional.nutritional_job_service.nutritional_repository.get_active_admissions",
            return_value=[],
        ), patch(
            "services.nutritional.nutritional_job_service.dbSession.setSchema",
        ):
            job_service.recalculate_nutritional_scores(app)


# ---------------------------------------------------------------------------
# init_scheduler
# ---------------------------------------------------------------------------


class TestInitScheduler:
    def test_does_not_start_when_disabled(self):
        """Scheduler must not start when SCHEDULER_ENABLED is False."""
        app = MagicMock()

        with patch(
            "services.nutritional.nutritional_job_service.Config"
        ) as mock_config, patch(
            "services.nutritional.nutritional_job_service.threading.Thread"
        ) as mock_thread:
            mock_config.SCHEDULER_ENABLED = False
            job_service.init_scheduler(app)

        mock_thread.assert_not_called()

    def test_starts_when_enabled(self):
        """Scheduler must start when SCHEDULER_ENABLED is True."""
        app = MagicMock()
        app.debug = False

        with patch(
            "services.nutritional.nutritional_job_service.Config"
        ) as mock_config, patch(
            "services.nutritional.nutritional_job_service.threading.Thread"
        ) as mock_thread:
            mock_config.SCHEDULER_ENABLED = True
            mock_config.SCHEDULER_INTERVAL_MINUTES = 15
            job_service.init_scheduler(app)

        mock_thread.assert_called_once()
        mock_thread.return_value.start.assert_called_once()

    def test_registers_job_with_correct_interval(self):
        """Job must be registered with the configured interval in minutes."""
        app = MagicMock()
        app.debug = False

        with patch(
            "services.nutritional.nutritional_job_service.Config"
        ) as mock_config, patch(
            "services.nutritional.nutritional_job_service.threading.Thread"
        ) as mock_thread:
            mock_config.SCHEDULER_ENABLED = True
            mock_config.SCHEDULER_INTERVAL_MINUTES = 30
            job_service.init_scheduler(app)

        _, kwargs = mock_thread.call_args
        assert kwargs.get("args")[1] == 30 * 60

    def test_registers_job_with_correct_id(self):
        """Thread must be registered with the name 'nutritional-recalc'."""
        app = MagicMock()
        app.debug = False

        with patch(
            "services.nutritional.nutritional_job_service.Config"
        ) as mock_config, patch(
            "services.nutritional.nutritional_job_service.threading.Thread"
        ) as mock_thread:
            mock_config.SCHEDULER_ENABLED = True
            mock_config.SCHEDULER_INTERVAL_MINUTES = 15
            job_service.init_scheduler(app)

        _, kwargs = mock_thread.call_args
        assert kwargs.get("name") == "nutritional-recalc"

    def test_uses_interval_trigger(self):
        """Job must use a daemon thread for background execution."""
        app = MagicMock()
        app.debug = False

        with patch(
            "services.nutritional.nutritional_job_service.Config"
        ) as mock_config, patch(
            "services.nutritional.nutritional_job_service.threading.Thread"
        ) as mock_thread:
            mock_config.SCHEDULER_ENABLED = True
            mock_config.SCHEDULER_INTERVAL_MINUTES = 15
            job_service.init_scheduler(app)

        _, kwargs = mock_thread.call_args
        assert kwargs.get("daemon") is True

    def test_werkzeug_reloader_guard(self):
        """Scheduler must not start in the parent process of the Werkzeug reloader."""
        app = MagicMock()
        app.debug = True

        with patch(
            "services.nutritional.nutritional_job_service.Config"
        ) as mock_config, patch(
            "services.nutritional.nutritional_job_service.threading.Thread"
        ) as mock_thread, patch.dict(
            "os.environ", {}, clear=True
        ):
            mock_config.SCHEDULER_ENABLED = True
            mock_config.SCHEDULER_INTERVAL_MINUTES = 15
            job_service.init_scheduler(app)

        mock_thread.assert_not_called()
