from decorators.has_permission_decorator import has_permission
from datetime import datetime

from repository.nutritional import nutritional_repository
from security.permission import Permission
import logging

@has_permission(Permission.READ_PRESCRIPTION)
def get_patients():
    """
    Busca pacientes usando o repositório com tratamento de erro.
    """
    try:
        return nutritional_repository.get_patients_repository()
    except Exception as e:

        logging.error(f"Erro ao buscar pacientes no repositório: {str(e)}")


        raise Exception("Estamos com problemas para consultar pacientes em nossa base, tente novamente mais tarde")

def calculate_mnutric(patient, apache, sofa) -> int:
    today = datetime.now()
    UtiDays = today.date() - patient.admissionDate.date()

    mn_age = _mn_Age(patient.birthdate)
    mn_apache = _mn_ApacheII(apache)
    mn_sofa = _mn_Sofa(sofa)
    mn_comorbity = _mn_Comorbity(patient.id_icd)
    mn_daysUTI = _mn_DaysUTI(UtiDays)

    mnutric = sum(v for v in [mn_age, mn_sofa, mn_comorbity, mn_daysUTI, mn_apache]
                if v is not None)
    return mnutric

def _mn_Age(birthDate): #considerando que seja um datetime
    mn_age = 0
    today = datetime.now()
    age = (today.year - birthDate.year)
    if(today.month, today.day) < (birthDate.month, birthDate.day):
        age -=1
    if age >= 50 and age < 75:
        mn_age = 1
    if age >= 75:
        mn_age = 2
    return mn_age

def _mn_ApacheII(apacheII): #recebe um int
    mn_ApacheII = 0
    if apacheII >= 15 and apacheII < 20:
        mn_ApacheII = 1
    if apacheII >= 20 and apacheII < 28:
        mn_ApacheII = 2
    if apacheII >= 28:
        mn_ApacheII = 3
    return mn_ApacheII

def _mn_Sofa(sofa): #recebe um int
    mn_Sofa = 0
    if sofa >= 6 and sofa < 10:
        mn_Sofa = 1
    if sofa >= 10:
        mn_Sofa = 2
    return mn_Sofa

def _mn_Comorbity(comorbity): #considerando que comorbidade seja uma lista de CID
    mn_Comorbity = 0
    if comorbity.length()>1:
        mn_Comorbity = 1
    return mn_Comorbity

def _mn_DaysUTI(daysUTI):
    mn_DaysUTI = 0
    if daysUTI > 1:
        mn_DaysUTI = 1
    return mn_DaysUTI