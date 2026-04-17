"""Nutritional job service — US-BE-06.

Periodic recalculation of Campo 1 scores (NRS-2002 and mNUTRIC) for all
active admissions. Scheduled via APScheduler with a configurable interval
(default: 15 minutes).

Dependencies: US-BE-04 (NRS engine) and US-BE-05 (mNUTRIC engine) must be
implemented before this job can perform actual score updates.
"""

import atexit
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError

from apscheduler.schedulers.background import BackgroundScheduler

from types import SimpleNamespace

from config import Config
from models.main import db
from repository.nutritional import nutritional_repository
from services.nutritional import nutritional_patient_service
from services.nutritional import nutritional_nrs_service
from services.nutritional.nutritional_nrs_service import is_uti

logger = logging.getLogger("noharm.nutritional")

scheduler = BackgroundScheduler()


def recalculate_nutritional_scores(app):
    """Recalculate Campo 1 scores for all active admissions.

    Processes each active admission independently so that an error in one
    patient does not interrupt the rest of the batch. Logs total processed
    count and error count at the end of each run.

    Args:
        app: Flask application instance — needed to push an app context
             inside the executor thread, which does not inherit the caller's context.
    """
    with app.app_context():
        logger.info("Iniciando recalculo de scores nutricionais (schema=%s)...", Config.SCHEDULER_SCHEMA)
        patients = nutritional_repository.get_active_admissions(schema=Config.SCHEDULER_SCHEMA)
        processed, errors = 0, 0

        for patient in patients:
            try:
                if is_uti(patient.nratendimento):
                    result = nutritional_patient_service.recalculate_mnutric(patient)

                    if result is None:
                        logger.error(
                            "Falha ao recalcular mNUTRIC para nratendimento=%s: retorno None",
                            patient.nratendimento,
                        )
                        errors += 1
                        continue

                    logger.info(
                        "mNUTRIC recalculado com sucesso para nratendimento=%s",
                        patient.nratendimento,
                    )
                else:
                    patient_ns = SimpleNamespace(
                        admissionNumber=patient.nratendimento,
                        birthdate=patient.dtnascimento,
                        id_icd=patient.idcid or "",
                    )
                    nutritional_nrs_service.recalculate_nrs(patient_ns)
                    logger.info(
                        "NRS-2002 recalculado com sucesso para nratendimento=%s",
                        patient.nratendimento,
                    )

                db.session.commit()
                processed += 1
            except Exception as e:
                db.session.rollback()
                logger.error(
                    "Erro ao recalcular nratendimento=%s: %s",
                    patient.nratendimento,
                    e,
                    exc_info=True,
                )
                errors += 1

        logger.info(
            "Recalculo concluido. Processados: %d, Erros: %d", processed, errors
        )


def init_scheduler(app):
    """Register and start the scheduler bound to the Flask app context.

    Should be called once from the app factory. Reads SCHEDULER_ENABLED and
    SCHEDULER_INTERVAL_MINUTES from Config to allow disabling the job in
    test/CI environments.

    Guards against Werkzeug's development reloader, which spawns two processes:
    only the child process (WERKZEUG_RUN_MAIN=true) starts the scheduler.

    Args:
        app: Flask application instance (needed for app context inside the job)
    """
    if not Config.SCHEDULER_ENABLED:
        logger.info("Scheduler desabilitado (SCHEDULER_ENABLED=false).")
        return

    # Werkzeug reloader guard: avoid starting two schedulers in development
    if app.debug and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        return

    interval_minutes = Config.SCHEDULER_INTERVAL_MINUTES

    timeout_seconds = Config.SCHEDULER_JOB_TIMEOUT_SECONDS

    def _job_with_context():
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(recalculate_nutritional_scores, app)
            try:
                future.result(timeout=timeout_seconds)
            except FuturesTimeoutError:
                logger.error(
                    "[US-BE-06] Job excedeu timeout de %ds e foi interrompido.",
                    timeout_seconds,
                )

    scheduler.add_job(
        _job_with_context,
        trigger="interval",
        minutes=interval_minutes,
        id="nutritional_score_recalc",
        replace_existing=True,
    )
    scheduler.start()
    atexit.register(lambda: scheduler.running and scheduler.shutdown(wait=False))

    logger.info(
        "Scheduler iniciado. Job nutritional_score_recalc a cada %d min.",
        interval_minutes,
    )
