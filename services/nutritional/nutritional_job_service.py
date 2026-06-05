"""Nutritional job service — US-BE-06 / US-BE-16.

Periodic recalculation of Campo 1 scores (NRS-2002 and mNUTRIC) and Campo 3
alerts (clin/rx) for all active admissions across every active tenant schema.

Runs outside the JWT request context: schema is set manually via
dbSession.setSchema() before each database operation, and re-set after
every commit/rollback (SQLAlchemy releases the connection on transaction end).
"""

import logging
import os
import threading
import time
from types import SimpleNamespace

from config import Config
from models.main import User, db, dbSession
from repository.nutritional import nutritional_repository
from repository.nutritional.nutritional_nrs_repository import get_patient_department
from services.nutritional import nutritional_nrs_service, nutritional_patient_service
from services.nutritional.nutritional_clin_rx_service import nutritional_alert_engine
from services.nutritional.nutritional_nrs_service import is_uti_wrapper

logger = logging.getLogger("noharm.nutritional")

_last_run: dict = {"at": None, "processed": 0, "errors": 0, "duration_ms": 0}


def _get_active_schemas() -> list:
    """Return all distinct schemas with at least one active user.

    Queries public.usuario — always accessible without schema_translate_map
    because User.__table_args__ has schema='public'.
    """
    rows = (
        db.session.query(User.schema)
        .filter(User.active == True)
        .distinct()
        .all()
    )
    return [r[0] for r in rows]


def _recalculate_schema(schema: str) -> tuple:
    """Recalculate Campo 1 scores and Campo 3 alerts for all active admissions.

    Sets schema_translate_map + search_path before each operation so that
    both ORM queries and raw SQL resolve to the correct tenant tables.

    Returns (processed, errors) counts.
    """
    logger.info("Iniciando recalculo schema=%s", schema)

    dbSession.setSchema(schema)
    patients = nutritional_repository.get_active_admissions(schema=schema)
    processed, errors = 0, 0

    for patient in patients:
        # Re-set after every commit/rollback — SQLAlchemy releases the connection
        # that held schema_translate_map on transaction end.
        dbSession.setSchema(schema)
        try:
            patient_is_icu = is_uti_wrapper(
                patient.nratendimento,
                get_patient_segment_type_fn=lambda _: patient.tp_segmento,
                get_patient_department_fn=get_patient_department,
            )
            patient_ns = SimpleNamespace(
                admissionNumber=patient.nratendimento,
                birthdate=patient.dtnascimento,
                id_icd=patient.idcid or "",
            )

            if patient_is_icu:
                result = nutritional_patient_service.recalculate_mnutric(patient)
                if result is None:
                    logger.error(
                        "Falha mNUTRIC nratendimento=%s schema=%s: retorno None",
                        patient.nratendimento,
                        schema,
                    )
                    errors += 1
                logger.info(
                    "mNUTRIC recalculado nratendimento=%s schema=%s",
                    patient.nratendimento,
                    schema,
                )

            nutritional_nrs_service.recalculate_nrs(patient_ns, is_icu=patient_is_icu)
            logger.info(
                "NRS-2002 recalculado nratendimento=%s schema=%s",
                patient.nratendimento,
                schema,
            )

            # Campo 3 alerts — isolated so failures never revert NRS/mNUTRIC commit
            try:
                nutritional_alert_engine()
                logger.info(
                    "Alertas Campo 3 processados nratendimento=%s schema=%s",
                    patient.nratendimento,
                    schema,
                )
            except Exception as trigger_err:
                logger.warning(
                    "Falha alertas nratendimento=%s schema=%s: %s",
                    patient.nratendimento,
                    schema,
                    trigger_err,
                )

            db.session.commit()
            processed += 1
        except Exception as e:
            db.session.rollback()
            logger.error(
                "Erro nratendimento=%s schema=%s: %s",
                patient.nratendimento,
                schema,
                e,
                exc_info=True,
            )
            errors += 1

    logger.info(
        "schema=%s concluido. Processados: %d, Erros: %d",
        schema,
        processed,
        errors,
    )
    return processed, errors


def recalculate_nutritional_scores(app):
    """Recalculate Campo 1 scores and Campo 3 alerts for every active tenant schema.

    Called by the background thread and by the manual trigger endpoint
    POST /nutritional/job/run. Pushes its own app context so it can run
    inside a thread that does not inherit the caller's context.

    Args:
        app: Flask application instance.
    """
    global _last_run

    start = time.monotonic()

    with app.app_context():
        schemas = _get_active_schemas()
        logger.info(
            "Iniciando recalculo nutricional: %d schema(s) encontrado(s): %s",
            len(schemas),
            schemas,
        )

        total_processed, total_errors = 0, 0
        for schema in schemas:
            try:
                processed, errors = _recalculate_schema(schema)
                total_processed += processed
                total_errors += errors
            except Exception as e:
                logger.error(
                    "Erro inesperado no schema=%s: %s", schema, e, exc_info=True
                )

        duration_ms = round((time.monotonic() - start) * 1000)

        _last_run = {
            "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "processed": total_processed,
            "errors": total_errors,
            "duration_ms": duration_ms,
        }

        logger.info(
            "Recalculo concluido. Total processados: %d, Total erros: %d, Duracao: %dms",
            total_processed,
            total_errors,
            duration_ms,
        )


def _scheduler_loop(app, interval_seconds: int) -> None:
    while True:
        time.sleep(interval_seconds)
        try:
            recalculate_nutritional_scores(app)
        except Exception:
            logger.exception("[US-BE-06] Falha inesperada no ciclo do job.")


def init_scheduler(app) -> None:
    """Start the background recalculation thread bound to the Flask app.

    Should be called once from the app factory. Reads SCHEDULER_ENABLED and
    SCHEDULER_INTERVAL_MINUTES from Config to allow disabling the job in
    test/CI environments.

    Guards against Werkzeug's development reloader, which spawns two processes:
    only the child process (WERKZEUG_RUN_MAIN=true) starts the thread.

    Args:
        app: Flask application instance (needed for app context inside the job)
    """
    if not Config.SCHEDULER_ENABLED:
        logger.info("Scheduler desabilitado (SCHEDULER_ENABLED=false).")
        return

    if app.debug and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        return

    interval_seconds = Config.SCHEDULER_INTERVAL_MINUTES * 60

    t = threading.Thread(
        target=_scheduler_loop,
        args=(app, interval_seconds),
        daemon=True,
        name="nutritional-recalc",
    )
    t.start()

    logger.info(
        "Scheduler iniciado (thread daemon). Recalculo a cada %d min.",
        Config.SCHEDULER_INTERVAL_MINUTES,
    )
