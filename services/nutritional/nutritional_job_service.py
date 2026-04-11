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

from apscheduler.schedulers.background import BackgroundScheduler

from config import Config
from models.appendix import SchemaConfig
from models.enums import IntegrationStatusEnum
from models.main import db
from repository.nutritional import nutritional_repository

logger = logging.getLogger("noharm.nutritional")

scheduler = BackgroundScheduler()


def recalculate_nutritional_scores():
    """Recalculate Campo 1 scores for all active admissions.

    Processes each active admission independently so that an error in one
    patient does not interrupt the rest of the batch. Logs total processed
    count and error count at the end of each run.
    """
    from datetime import datetime

    logger.info("=" * 60)
    logger.info("[US-BE-06] Recalculo iniciado em %s", datetime.now().isoformat())

    schemas = (
        db.session.query(SchemaConfig.schemaName)
        .filter(SchemaConfig.status != IntegrationStatusEnum.CANCELED.value)
        .all()
    )
    logger.info("[US-BE-06] Schemas ativos encontrados: %d", len(schemas))

    total_processed, total_errors = 0, 0

    for (schema_name,) in schemas:
        try:
            patients = nutritional_repository.get_active_admissions(schema=schema_name)
            logger.info(
                "[US-BE-06] Schema=%s | Admissoes ativas: %d", schema_name, len(patients)
            )
        except Exception as e:
            logger.error("[US-BE-06] Erro ao buscar admissoes do schema=%s: %s", schema_name, e)
            db.session.rollback()
            continue

        for patient in patients:
            try:
                if patient.is_icu:
                    logger.info(
                        "[US-BE-06] schema=%s nratendimento=%s -> mNUTRIC (UTI)",
                        schema_name,
                        patient.nratendimento,
                    )
                    # TODO (US-BE-05): nutritional_score_service.recalculate_mnutric(patient)
                else:
                    logger.info(
                        "[US-BE-06] schema=%s nratendimento=%s -> NRS-2002",
                        schema_name,
                        patient.nratendimento,
                    )
                    # TODO (US-BE-04): nutritional_score_service.recalculate_nrs(patient)

                total_processed += 1
            except Exception as e:
                logger.error(
                    "Erro ao recalcular schema=%s nratendimento=%s: %s",
                    schema_name,
                    patient.nratendimento,
                    e,
                    exc_info=True,
                )
                total_errors += 1

    logger.info(
        "[US-BE-06] Recalculo concluido. Processados: %d, Erros: %d, Horario: %s",
        total_processed,
        total_errors,
        datetime.now().isoformat(),
    )
    logger.info("=" * 60)


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

    def _job_with_context():
        with app.app_context():
            recalculate_nutritional_scores()

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
