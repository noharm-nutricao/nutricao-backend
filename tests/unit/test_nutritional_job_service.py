"""Unit tests for nutritional_job_service (US-BE-06 / US-BE-25).

Tests cover:
- recalculate_nutritional_scores: tolerance to per-patient failures, protocol
  selection (MNUTRIC vs NRS2002), processing counters and logging.
- init_scheduler: respects SCHEDULER_ENABLED flag, starts daemon thread with
  correct name, guards against Werkzeug reloader double-start.
- triagem_at: idempotent guard that records first complete NRS as triagem.
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import services.nutritional.nutritional_job_service as job_service
from services.nutritional.nutritional_dtos import NrsScoreDTO
from mobile import app as flask_app


def _make_nrs_dto(nrs_completo=True):
    return NrsScoreDTO(
        id=1,
        nrs_nut=2,
        nrs_doenca=1,
        nrs_idade=0,
        nrs_total=3,
        classificacao="al",
        nrs_completo=nrs_completo,
        nrs_ref_at=datetime.now(timezone.utc),
        calculado_at=datetime.now(timezone.utc),
    )


def _make_patient(nratendimento, is_icu, tp_segmento=None, dtnascimento=None, idcid=None):
    return SimpleNamespace(
        nratendimento=nratendimento,
        is_icu=is_icu,
        tp_segmento=tp_segmento,
        dtnascimento=dtnascimento,
        idcid=idcid,
    )


def _icu_side_effect(patients):
    """Returns is_uti_wrapper side_effect that mirrors patient.is_icu by nratendimento."""
    m = {p.nratendimento: p.is_icu for p in patients}
    return lambda n, **kw: m.get(n, False)


# ---------------------------------------------------------------------------
# recalculate_nutritional_scores
# ---------------------------------------------------------------------------


class TestRecalculateNutritionalScores:
    def test_processes_all_active_admissions(self):
        """Every patient returned by get_active_admissions is visited."""
        patients = [_make_patient(1, False), _make_patient(2, True)]

        with patch(
            "services.nutritional.nutritional_job_service._get_active_schemas",
            return_value=["demo"],
        ), patch(
            "services.nutritional.nutritional_job_service.nutritional_repository.get_active_admissions",
            return_value=patients,
        ), patch(
            "services.nutritional.nutritional_job_service.is_uti_wrapper",
            side_effect=_icu_side_effect(patients),
        ), patch(
            "services.nutritional.nutritional_job_service.nutritional_patient_service.recalculate_mnutric",
            return_value={"total": 5},
        ) as mock_mnutric, patch(
            "services.nutritional.nutritional_job_service.nutritional_nrs_service.recalculate_nrs",
            return_value=(_make_nrs_dto(nrs_completo=False), None),
        ) as mock_nrs, patch(
            "services.nutritional.nutritional_job_service.db.session.commit",
        ) as mock_commit:
            job_service.recalculate_nutritional_scores(flask_app)

        assert mock_nrs.call_count == 2       # ambos os pacientes passam por NRS
        assert mock_mnutric.call_count == 1   # apenas paciente ICU passa por mNUTRIC
        assert mock_commit.call_count == 2    # commit por paciente processado com sucesso
        for call_item, patient in zip(mock_nrs.call_args_list, patients, strict=True):
            assert call_item.kwargs.get("is_icu") == patient.is_icu

    def test_tolerates_single_patient_failure(self):
        """An exception on one patient must not interrupt the rest of the batch."""
        patients = [
            _make_patient(1, False),
            _make_patient(2, True),   # this one will fail (ICU → calls mnutric)
            _make_patient(3, False),
        ]

        with patch(
            "services.nutritional.nutritional_job_service._get_active_schemas",
            return_value=["demo"],
        ), patch(
            "services.nutritional.nutritional_job_service.nutritional_repository.get_active_admissions",
            return_value=patients,
        ), patch(
            "services.nutritional.nutritional_job_service.is_uti_wrapper",
            side_effect=_icu_side_effect(patients),
        ), patch(
            "services.nutritional.nutritional_job_service.nutritional_patient_service.recalculate_mnutric",
            side_effect=ValueError("Simulated error"),
        ), patch(
            "services.nutritional.nutritional_job_service.nutritional_nrs_service.recalculate_nrs",
            return_value=(_make_nrs_dto(nrs_completo=False), None),
        ), patch(
            "services.nutritional.nutritional_job_service.db.session.commit",
        ), patch(
            "services.nutritional.nutritional_job_service.db.session.rollback",
        ), patch.object(job_service.logger, "error") as mock_error:
            job_service.recalculate_nutritional_scores(flask_app)

        assert mock_error.call_count == 1

    def test_logs_error_for_icu_patient_when_recalculation_returns_none(self):
        """mNUTRIC returning None is logged as an error, but NRS-2002 must still
        run and be committed for the ICU patient (the two scores are independent).
        """
        patients = [_make_patient(10, True)]

        with patch(
            "services.nutritional.nutritional_job_service._get_active_schemas",
            return_value=["demo"],
        ), patch(
            "services.nutritional.nutritional_job_service.nutritional_repository.get_active_admissions",
            return_value=patients,
        ), patch(
            "services.nutritional.nutritional_job_service.is_uti_wrapper",
            side_effect=_icu_side_effect(patients),
        ), patch(
            "services.nutritional.nutritional_job_service.nutritional_patient_service.recalculate_mnutric",
            return_value=None,
        ), patch(
            "services.nutritional.nutritional_job_service.nutritional_nrs_service.recalculate_nrs",
            return_value=(_make_nrs_dto(nrs_completo=False), None),
        ), patch(
            "services.nutritional.nutritional_job_service.db.session.commit",
        ) as mock_commit, patch.object(job_service.logger, "error") as mock_error:
            job_service.recalculate_nutritional_scores(flask_app)

        mock_commit.assert_called_once()
        assert any("retorno None" in str(call) for call in mock_error.call_args_list)

    def test_logs_summary_after_run(self):
        """A summary info log must be emitted at the end of each execution."""
        patients = [_make_patient(1, False), _make_patient(2, True)]

        with patch(
            "services.nutritional.nutritional_job_service._get_active_schemas",
            return_value=["demo"],
        ), patch(
            "services.nutritional.nutritional_job_service.nutritional_repository.get_active_admissions",
            return_value=patients,
        ), patch(
            "services.nutritional.nutritional_job_service.is_uti_wrapper",
            side_effect=_icu_side_effect(patients),
        ), patch(
            "services.nutritional.nutritional_job_service.nutritional_patient_service.recalculate_mnutric",
            return_value={"total": 5},
        ), patch(
            "services.nutritional.nutritional_job_service.nutritional_nrs_service.recalculate_nrs",
            return_value=(_make_nrs_dto(nrs_completo=False), None),
        ), patch(
            "services.nutritional.nutritional_job_service.db.session.commit",
        ), patch.object(job_service.logger, "info") as mock_info:
            job_service.recalculate_nutritional_scores(flask_app)

        assert mock_info.call_count >= 2
        last_call = str(mock_info.call_args_list[-1])
        assert "Processados" in last_call or "concluido" in last_call.lower()

    def test_empty_admission_list_runs_without_error(self):
        """Job must complete normally when there are no active admissions."""
        with patch(
            "services.nutritional.nutritional_job_service._get_active_schemas",
            return_value=["demo"],
        ), patch(
            "services.nutritional.nutritional_job_service.nutritional_repository.get_active_admissions",
            return_value=[],
        ):
            job_service.recalculate_nutritional_scores(flask_app)


# ---------------------------------------------------------------------------
# init_scheduler
# ---------------------------------------------------------------------------


class TestInitScheduler:
    def test_does_not_start_when_disabled(self):
        """Scheduler must not start a thread when SCHEDULER_ENABLED is False."""
        app = MagicMock()
        app.debug = False

        with patch(
            "services.nutritional.nutritional_job_service.Config"
        ) as mock_config, patch(
            "services.nutritional.nutritional_job_service.threading.Thread"
        ) as mock_thread_cls:
            mock_config.SCHEDULER_ENABLED = False

            job_service.init_scheduler(app)

        mock_thread_cls.assert_not_called()

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


# ---------------------------------------------------------------------------
# triagem_at guard (US-BE-25)
# ---------------------------------------------------------------------------


class TestTriagemAt:
    def _run_job_n_times(self, patients, triagem_mock, nrs_completo, n=1):
        """Helper: run recalculate_nutritional_scores n times."""
        for _ in range(n):
            with patch(
                "services.nutritional.nutritional_job_service._get_active_schemas",
                return_value=["demo"],
            ), patch(
                "services.nutritional.nutritional_job_service.nutritional_repository.get_active_admissions",
                return_value=patients,
            ), patch(
                "services.nutritional.nutritional_job_service.is_uti_wrapper",
                side_effect=_icu_side_effect(patients),
            ), patch(
                "services.nutritional.nutritional_job_service.nutritional_patient_service.recalculate_mnutric",
                return_value={"total": 5},
            ), patch(
                "services.nutritional.nutritional_job_service.nutritional_nrs_service.recalculate_nrs",
                return_value=(_make_nrs_dto(nrs_completo=nrs_completo), triagem_mock),
            ), patch(
                "services.nutritional.nutritional_job_service.db.session.commit",
            ):
                job_service.recalculate_nutritional_scores(flask_app)

    def test_triagem_at_set_only_on_first_complete_run(self):
        """Job executa 3x para mesmo paciente -> triagem_at gravado apenas na primeira vez."""
        patients = [_make_patient(1, False)]
        triagem_mock = MagicMock()
        triagem_mock.triagem_at = None

        self._run_job_n_times(patients, triagem_mock, nrs_completo=True, n=1)

        assert triagem_mock.triagem_at is not None
        first_triagem_at = triagem_mock.triagem_at

        self._run_job_n_times(patients, triagem_mock, nrs_completo=True, n=2)

        assert triagem_mock.triagem_at == first_triagem_at

    def test_triagem_at_stays_null_when_nrs_incomplete(self):
        """Job executa, paciente sem NRS completo -> triagem_at permanece null."""
        patients = [_make_patient(1, False)]
        triagem_mock = MagicMock()
        triagem_mock.triagem_at = None
        triagem_mock.nrs_completo = False

        self._run_job_n_times(patients, triagem_mock, nrs_completo=False, n=1)

        assert triagem_mock.triagem_at is None

    def test_manual_save_sets_triagem_at_when_null(self):
        """Save manual NRS completo -> triagem_at registrado se ainda null."""
        triagem_mock = MagicMock()
        triagem_mock.nrs_completo = True
        triagem_mock.triagem_at = None

        with patch(
            "services.nutritional.nutritional_patient_service.get_or_create_triagem",
            return_value=triagem_mock,
        ), patch(
            "services.nutritional.nutritional_patient_service.nutritional_repository.get_patients_repository",
            return_value=[{"id": 42}],
        ), patch(
            "services.nutritional.nutritional_patient_service.nutritional_repository.create_assessment",
        ), patch(
            "services.nutritional.nutritional_patient_service.db.session.flush",
        ):
            from services.nutritional import nutritional_patient_service

            data = SimpleNamespace(
                conduta="teste",
                frequencia="24h",
                ingestao=80,
                meta_kcal=2000,
                meta_prot=100,
                prox_visita="24h",
            )
            nutritional_patient_service.create_assessment.__wrapped__(
                nratendimento=42, data=data, idusuario=1
            )

        assert triagem_mock.triagem_at is not None

    def test_manual_save_does_not_overwrite_existing_triagem_at(self):
        """Save manual NRS apos triagem existente -> triagem_at nao alterado."""
        existing_dt = datetime(2025, 1, 1, tzinfo=timezone.utc)
        triagem_mock = MagicMock()
        triagem_mock.nrs_completo = True
        triagem_mock.triagem_at = existing_dt

        with patch(
            "services.nutritional.nutritional_patient_service.get_or_create_triagem",
            return_value=triagem_mock,
        ), patch(
            "services.nutritional.nutritional_patient_service.nutritional_repository.get_patients_repository",
            return_value=[{"id": 42}],
        ), patch(
            "services.nutritional.nutritional_patient_service.nutritional_repository.create_assessment",
        ), patch(
            "services.nutritional.nutritional_patient_service.db.session.flush",
        ):
            from services.nutritional import nutritional_patient_service

            data = SimpleNamespace(
                conduta="teste",
                frequencia="24h",
                ingestao=80,
                meta_kcal=2000,
                meta_prot=100,
                prox_visita="24h",
            )
            nutritional_patient_service.create_assessment.__wrapped__(
                nratendimento=42, data=data, idusuario=1
            )

        assert triagem_mock.triagem_at == existing_dt
