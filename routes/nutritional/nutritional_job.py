"""Nutritional job diagnostic routes.

Provides a manually-triggered endpoint for testing and validating the
periodic recalculation job outside of the scheduler cycle.

Only available when ENV != production.
"""

from flask import Blueprint, jsonify

from config import Config
from decorators.api_endpoint_decorator import api_endpoint
from models.enums import NoHarmENV
from services.nutritional import nutritional_job_service

app_nutritional_job = Blueprint("app_nutritional_job", __name__)


@app_nutritional_job.route("/nutritional/job/run", methods=["POST"])
@api_endpoint()
def run_job():
    """Trigger the nutritional score recalculation job immediately.

    For diagnostic and testing purposes only. Returns a 403 in production.
    """
    if Config.ENV == NoHarmENV.PRODUCTION.value:
        return jsonify({"error": "Not available in production"}), 403

    nutritional_job_service.recalculate_nutritional_scores()
    return {"status": "ok", "message": "Job executado. Verifique os logs."}


@app_nutritional_job.route("/nutritional/job/status", methods=["GET"])
@api_endpoint()
def job_status():
    """Return the current scheduler status and next run time.

    For diagnostic and testing purposes only. Returns a 403 in production.
    """
    if Config.ENV == NoHarmENV.PRODUCTION.value:
        return jsonify({"error": "Not available in production"}), 403

    scheduler = nutritional_job_service.scheduler
    job = scheduler.get_job("nutritional_score_recalc")

    if not scheduler.running:
        return {"scheduler": "stopped", "job": None}

    return {
        "scheduler": "running",
        "job": {
            "id": job.id if job else None,
            "next_run": job.next_run_time.isoformat() if job and job.next_run_time else None,
        },
    }
