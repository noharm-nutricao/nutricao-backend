"""Nutritional job diagnostic routes.

Provides a manually-triggered endpoint for testing and validating the
periodic recalculation job outside of the scheduler cycle.

Only available in non-production environments — enforced by is_admin=True,
which already raises AuthorizationError in production via api_endpoint_decorator.
"""

import logging

from flask import Blueprint, current_app

from decorators.api_endpoint_decorator import api_endpoint
from services.nutritional import nutritional_job_service

logger = logging.getLogger("noharm.nutritional")

app_nutritional_job = Blueprint("app_nutritional_job", __name__)


@app_nutritional_job.route("/nutritional/job/run", methods=["POST"])
@api_endpoint(is_admin=True)
def run_job():
    """Trigger the nutritional score recalculation job immediately (all schemas)."""
    logger.info("[US-BE-06] Disparo manual do job solicitado via endpoint.")
    nutritional_job_service.recalculate_nutritional_scores(current_app._get_current_object())
    logger.info("[US-BE-06] Disparo manual concluido.")
    return {"message": "Job executado. Verifique os logs."}


@app_nutritional_job.route("/nutritional/job/status", methods=["GET"])
@api_endpoint(is_admin=True)
def job_status():
    """Return whether the background recalculation thread is alive."""
    import threading
    thread = next(
        (t for t in threading.enumerate() if t.name == "nutritional-recalc"),
        None,
    )
    return {
        "scheduler": "running" if thread and thread.is_alive() else "stopped",
        "thread": thread.name if thread else None,
    }
