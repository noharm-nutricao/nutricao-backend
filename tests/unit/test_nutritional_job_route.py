from unittest.mock import patch

from flask import Flask

from routes.nutritional.nutritional_job import app_nutritional_job


def _client():
    app = Flask(__name__)
    app.register_blueprint(app_nutritional_job)
    return app.test_client()


def test_run_job_requires_api_key():
    client = _client()

    with patch("routes.nutritional.nutritional_job.Config.API_KEY", "secret-key"), patch(
        "routes.nutritional.nutritional_job.nutritional_job_service.recalculate_nutritional_scores"
    ) as mock_job:
        response = client.post("/nutritional/job/run")

    assert response.status_code == 401
    assert response.get_json()["code"] == "error.authorizationError"
    mock_job.assert_not_called()


def test_run_job_accepts_valid_api_key():
    client = _client()

    with patch("routes.nutritional.nutritional_job.Config.API_KEY", "secret-key"), patch(
        "routes.nutritional.nutritional_job.nutritional_job_service.recalculate_nutritional_scores"
    ) as mock_job:
        response = client.post(
            "/nutritional/job/run",
            headers={"X-API-Key": "secret-key"},
        )

    assert response.status_code == 200
    assert response.get_json()["status"] == "success"
    mock_job.assert_called_once()


def test_status_requires_same_api_key():
    client = _client()

    with patch("routes.nutritional.nutritional_job.Config.API_KEY", "secret-key"):
        unauthorized = client.get("/nutritional/job/status")
        authorized = client.get(
            "/nutritional/job/status",
            headers={"X-API-Key": "secret-key"},
        )

    assert unauthorized.status_code == 401
    assert authorized.status_code == 200
    assert "scheduler" in authorized.get_json()["data"]
