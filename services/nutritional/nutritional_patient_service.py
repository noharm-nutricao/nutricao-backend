from repository.nutritional import nutritional_repository


def get_patients():
    """
    Busca pacientes usando o repositório com tratamento de erro.
    """
    try:
        return nutritional_repository.get_patients_repository()
    except Exception as e:

        print(f"Erro ao buscar pacientes: {str(e)}")

        # Lançamos uma exceção que a sua API capture ou retornamos uma mensagem clara
        # Se o projeto não tiver um Handler, você pode lançar um erro genérico:
        raise Exception("Estamos com problemas para consultar pacientes em nossa base, tente novamente mais tarde")

