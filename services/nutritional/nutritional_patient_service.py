from repository.nutritional import nutritional_repository
import logging


def get_patients():
    """
    Busca pacientes usando o repositório com tratamento de erro.
    """
    try:
        return nutritional_repository.get_patients_repository()
    except Exception as e:

        logging.error(f"Erro ao buscar pacientes no repositório: {str(e)}")


        raise Exception("Estamos com problemas para consultar pacientes em nossa base, tente novamente mais tarde")

