
# routes/nutritional/nutritional_patients.py
from flask import Blueprint
from decorators.api_endpoint_decorator import api_endpoint
from decorators.has_permission_decorator import has_permission
from security.permission import Permission

from services.nutritional import nutritional_patient_service

app_nutritional = Blueprint("app_nutritional", __name__)

@app_nutritional.route("/nutritional/patients", methods=["GET"])
@api_endpoint()
@has_permission(Permission.READ_PRESCRIPTION)
def get_patients():
    try:
        # Chama o service que agora só retorna os dados (ou o erro)
        data = nutritional_patient_service.get_patients()

        # SUCESSO
        return data, 200
    except Exception as e:
        # ERRO: Se o service der o 'raise Exception', cai aqui
        # Retornamos a mensagem amigável com 500
        return {"message": str(e)}, 500

