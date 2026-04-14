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


def save_manual_mnutric(admission_number: int, mnutric: dict):
    return nutritional_repository.save_manual_mnutric(
        admission_number=admission_number,
        mnutric=mnutric,
    )

def calculate_mnutric(patient, apache, sofa) -> dict:
    today             = datetime.now()
    uti_days          = (today.date() - patient.admissionDate.date()).days
    dados_incompletos = (apache is None) or (sofa is None)

    mnutric_age       = _mnutric_age(patient.birthdate)
    mnutric_apache    = _mnutric_apache_ii(apache) if apache is not None else 0
    mnutric_sofa      = _mnutric_sofa(sofa) if sofa is not None else 0
    mnutric_comorbity = _mnutric_comorbity(patient.id_icd)
    mnutric_days_uti  = _mnutric_days_uti(uti_days)
    mnutric           = (mnutric_age + mnutric_apache + mnutric_sofa + mnutric_comorbity + mnutric_days_uti)

    result = {
        "total"            : mnutric,
        "age"              : mnutric_age,
        "apache"           : mnutric_apache,
        "sofa"             : mnutric_sofa,
        "comorbity"        : mnutric_comorbity,
        "daysUTI"          : mnutric_days_uti,
        "classify"         : _mnutric_clasify(mnutric) if not dados_incompletos else None,
        "dados_incompletos": dados_incompletos,
    }

    if getattr(patient, "admissionNumber", None) is not None:
        save_manual_mnutric(admission_number=patient.admissionNumber, mnutric=result)

    return result

def _mnutric_age(birthDate) -> int:
    mnutric_age = 0
    today       = datetime.now()
    age         = (today.year - birthDate.year)
    if(today.month, today.day) < (birthDate.month, birthDate.day):
        age -= 1
    if age >= 50 and age < 75:
        mnutric_age = 1
    if age >= 75:
        mnutric_age = 2
    return mnutric_age

def _mnutric_apache_ii(apache_ii) -> int:
    mnutric_apache_ii = 0
    if apache_ii >= 15 and apache_ii < 20:
        mnutric_apache_ii = 1
    if apache_ii >= 20 and apache_ii < 28:
        mnutric_apache_ii = 2
    if apache_ii >= 28:
        mnutric_apache_ii = 3
    return mnutric_apache_ii

def _mnutric_sofa(sofa) -> int:
    mnutric_sofa = 0
    if sofa >= 6 and sofa < 10:
        mnutric_sofa = 1
    if sofa >= 10:
        mnutric_sofa = 2
    return mnutric_sofa

#TODO: verify if we can have in a single string more than one cid from patient
def _mnutric_comorbity(comorbity) -> int:
    mnutric_comorbity = 0
    if comorbity:
        mnutric_comorbity = 1
    return mnutric_comorbity

def _mnutric_days_uti(days_uti) -> int:
    mnutric_days_uti = 0
    if days_uti > 1:
        mnutric_days_uti = 1
    return mnutric_days_uti

def _mnutric_clasify(mnutric: int) -> str:
    if mnutric >= 0 and mnutric <= 2:
        return "bx"
    elif mnutric >= 3 and mnutric <= 4:
        return "md"
    elif mnutric >= 5 and mnutric <= 6:
        return "al"
    elif mnutric >= 7:
        return "cr"
    else:
        return "unknown"

def recalculate_mnutric(patient):
    from services import patient_service

    admission_number = getattr(patient, "nratendimento", None)
    birthdate = getattr(patient, "dtnascimento", None)
    admission_date = getattr(patient, "dtinternacao", None)

    if (admission_number is None) or (birthdate is None) or (admission_date is None):
        return None

    screening = nutritional_repository.get_saved_mnutric(admission_number)
    apache = getattr(screening, "mn_apache", None)
    sofa = getattr(screening, "mn_sofa", None)

    return calculate_mnutric(patient=patient, apache=apache, sofa=sofa)
