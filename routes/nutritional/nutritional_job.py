"""Nutritional job diagnostic routes.

Provides API key-protected endpoints for triggering and inspecting the
nutritional recalculation job without requiring JWT admin authentication.
"""

import json
import logging
import time
from functools import wraps
from hmac import compare_digest

from flask import Blueprint, current_app, request

from config import Config
from exception.authorization_error import AuthorizationError
from services.nutritional import nutritional_job_service
from utils import logger as request_logger
from utils import status

logger = logging.getLogger("noharm.nutritional")

app_nutritional_job = Blueprint("app_nutritional_job", __name__)


def api_key_endpoint():
    """Protect endpoint with the configured internal API key."""

    def wrapper(f):
        @wraps(f)
        def decorator_f(*args, **kwargs):
            start_time = time.time()
            try:
                provided_key = request.headers.get("X-API-Key", "")
                configured_key = Config.API_KEY or ""

                if (
                    not configured_key
                    or not compare_digest(provided_key, configured_key)
                ):
                    raise AuthorizationError()

                result = f(*args, **kwargs)
                return {"status": "success", "data": result}, status.HTTP_200_OK

            except AuthorizationError:
                request_logger.backend_logger.warning(
                    json.dumps(
                        {
                            "event": "validation_error",
                            "path": request.path,
                            "method": request.method,
                            "schema": "api_key",
                            "user": "api_key",
                            "message": "API key inválida no recurso",
                        }
                    )
                )
                return {
                    "status": "error",
                    "message": "Usuário não autorizado neste recurso",
                    "code": "error.authorizationError",
                }, status.HTTP_401_UNAUTHORIZED

            except Exception as e:
                request_logger.backend_logger.exception(str(e))
                request_logger.backend_logger.error(
                    "Request data: %s", request.get_data()
                )
                return {
                    "status": "error",
                    "message": "Ocorreu um erro inesperado",
                }, status.HTTP_500_INTERNAL_SERVER_ERROR

            finally:
                elapsed_time = round((time.time() - start_time) * 1000, 3)
                request_logger.backend_logger.warning(
                    json.dumps(
                        {
                            "event": "request_complete",
                            "path": request.path,
                            "method": request.method,
                            "duration_ms": elapsed_time,
                            "schema": "api_key",
                            "user": "api_key",
                        }
                    )
                )

        return decorator_f

    return wrapper


@app_nutritional_job.route("/nutritional/job/run", methods=["POST"])
@api_key_endpoint()
def run_job():
    """Trigger the nutritional score recalculation job immediately (all schemas)."""
    logger.info("[US-BE-06] Disparo manual do job solicitado via endpoint.")
    nutritional_job_service.recalculate_nutritional_scores(current_app._get_current_object())
    logger.info("[US-BE-06] Disparo manual concluido.")
    return {"message": "Job executado. Verifique os logs."}


@app_nutritional_job.route("/nutritional/job/status", methods=["GET"])
@api_key_endpoint()
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
