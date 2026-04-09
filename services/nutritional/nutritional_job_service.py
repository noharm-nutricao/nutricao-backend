
import logging

from apscheduler.schedulers.background import BackgroundScheduler

from config import Config
from repository.nutritional import nutritional_repository

logger = logging.getLogger("noharm.nutritional")

scheduler = BackgroundScheduler()


def recalculate_nutritional_scores():
    """Recalculate Campo 1 scores for all active admissions.

    """
    logger.info("Iniciando recalculo de scores nutricionais...")
    patients = nutritional_repository.get_active_admissions()
    processed, errors = 0, 0

    for patient in patients:
        try:
            protocol = "MNUTRIC" if patient.is_icu else "NRS2002"

            if protocol == "MNUTRIC":
                # TODO (US-BE-05): implement nutritional_score_service.recalculate_mnutric
                pass
            else:
                # TODO (US-BE-04): implement nutritional_score_service.recalculate_nrs
                pass

            processed += 1
        except Exception as e:
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

    Args:
        app: Flask application instance (needed for app context inside the job)
    """
    if not Config.SCHEDULER_ENABLED:
        logger.info("Scheduler desabilitado (SCHEDULER_ENABLED=false).")
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
    logger.info(
        "Scheduler iniciado. Job nutritional_score_recalc a cada %d min.",
        interval_minutes,
    )
