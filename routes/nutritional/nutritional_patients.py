
# routes/nutritional/nutritional_patients.py
from flask import Blueprint
from decorators.api_endpoint_decorator import api_endpoint
from exception.validation_error import ValidationError

from services.nutritional import nutritional_patient_service
from utils import status

app_nutritional = Blueprint("app_nutritional", __name__)

@app_nutritional.route("/nutritional/patients", methods=["GET"])
@api_endpoint()
def get_patients():
    try:
        # Chama o service que agora só retorna os dados (ou o erro)
        data = nutritional_patient_service.get_patients()

        if data is None:
            raise ValidationError(
                "Nenhum paciente encontrado.",
                "errors.notFound",
                status.HTTP_404_NOT_FOUND
            )

        # SUCESSO
        return data
    except Exception as e:
        # ERRO: Se o service der o 'raise Exception', cai aqui
        # Retornamos a mensagem amigável com 500
        return {"message": str(e)}, 500

