from repository.nutritional import nutritional_repository

def get_patients():
    """
    Busca pacientes usando o repositório.
    """
    data = nutritional_repository.get_patients_repository()

    return data, 200
