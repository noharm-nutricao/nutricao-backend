from flask import Blueprint

app_nutritional_health = Blueprint("app_nutritional_health", __name__)


@app_nutritional_health.route("/nutritional/healthz", methods=["GET"])
def healthz():
    return {"Message": "Ok"}