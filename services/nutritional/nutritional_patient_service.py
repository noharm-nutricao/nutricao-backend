from decorators.has_permission_decorator import has_permission
from datetime import datetime
from types import SimpleNamespace

from models.prescription import Patient
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
    """Calcula e persiste mNUTRIC a partir de entrada manual (PUT /mnutric-manual).

    apache e sofa são os valores brutos informados pelo nutricionista.
    Seta mn_apache_manual=True e mn_sofa_manual=True via save_manual_mnutric.
    """
    mnutric_age       = _mnutric_age(patient.birthdate)
    mnutric_apache    = _mnutric_apache_ii(apache)
    mnutric_sofa      = _mnutric_sofa(sofa)
    mnutric_comorbity = _mnutric_comorbity(patient.id_icd)
    mnutric_days_uti  = _mnutric_days_before_icu(patient)
    mnutric           = mnutric_age + mnutric_apache + mnutric_sofa + mnutric_comorbity + mnutric_days_uti

    result = {
        "total"            : mnutric,
        "age"              : mnutric_age,
        "apache"           : mnutric_apache,
        "sofa"             : mnutric_sofa,
        "comorbity"        : mnutric_comorbity,
        "daysUTI"          : mnutric_days_uti,
        "classify"         : _mnutric_clasify(mnutric),
        "dados_incompletos": False,
    }

    if getattr(patient, "admissionNumber", None) is not None:
        try:
            save_manual_mnutric(admission_number=patient.admissionNumber, mnutric=result)
        except Exception as e:
            logging.error(
                "Falha ao persistir mNUTRIC para nratendimento=%s: %s",
                patient.admissionNumber,
                e,
            )

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

def _mnutric_comorbity(comorbity) -> int:
    mnutric_comorbity = 0
    if comorbity:
        mnutric_comorbity = 1
    return mnutric_comorbity

def _mnutric_days_before_icu(patient: Patient) -> int:
    admission_date = getattr(patient, "admissionDate", None) or getattr(patient, "dtinternacao", None)
    entry_date = (
        getattr(patient, "lastTransferDate", None)
        or getattr(patient, "utiEntryDate", None)
        or getattr(patient, "dt_ultima_transferencia", None)
        or admission_date
    )
    if admission_date is None or entry_date is None:
        return 0
    dias_antes_uti = (entry_date.date() - admission_date.date()).days
    return 1 if dias_antes_uti >= 2 else 0

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
    """Recalculo periódico pelo job — preserva flags manuais de APACHE/SOFA.

    dados_incompletos é derivado dos flags mn_apache_manual/mn_sofa_manual:
    se o nutricionista ainda não inseriu os valores via PUT, o reconhecimento
    permanece bloqueado no frontend.
    """
    admission_number = getattr(patient, "nratendimento", None)
    birthdate = getattr(patient, "dtnascimento", None)
    admission_date = getattr(patient, "dtinternacao", None)

    if (admission_number is None) or (birthdate is None) or (admission_date is None):
        logging.warning(
            "Recalculo mNUTRIC ignorado para nratendimento=%s: campos obrigatorios ausentes",
            admission_number,
        )
        return None

    normalized = SimpleNamespace(
        admissionNumber=admission_number,
        birthdate=birthdate,
        admissionDate=admission_date,
        utiEntryDate=getattr(patient, "lastTransferDate", None) or admission_date,
        id_icd=getattr(patient, "idcid", None) or '',
    )

    screening = nutritional_repository.get_saved_mnutric(admission_number)
    apache_manual = getattr(screening, "mn_apache_manual", False) or False
    sofa_manual = getattr(screening, "mn_sofa_manual", False) or False
    dados_incompletos = not apache_manual or not sofa_manual

    apache = _restore_apache_ii_from_dimension(getattr(screening, "mn_apache", None)) if apache_manual else None
    sofa = _restore_sofa_from_dimension(getattr(screening, "mn_sofa", None)) if sofa_manual else None

    result = {
        "age":          _mnutric_age(normalized.birthdate),
        "apache":       _mnutric_apache_ii(apache) if apache is not None else None,
        "sofa":         _mnutric_sofa(sofa) if sofa is not None else None,
        "comorbity":    _mnutric_comorbity(normalized.id_icd),
        "daysUTI":      _mnutric_days_before_icu(normalized),
        "dados_incompletos": dados_incompletos,
        "total":        None,
        "classify":     None,
    }

    if not dados_incompletos:
        result["total"] = sum(v for v in [result["age"], result["apache"], result["sofa"], result["comorbity"], result["daysUTI"]] if v is not None)
        result["classify"] = _mnutric_clasify(result["total"])

    nutritional_repository.update_mnutric_scores(admission_number, result)

    logging.info(
        "mNUTRIC recalculado para nratendimento=%s: total=%s, classify=%s, dados_incompletos=%s",
        admission_number,
        result["total"],
        result["classify"],
        result["dados_incompletos"],
    )

    return result

def _restore_apache_ii_from_dimension(score):
    if score is None:
        return None

    if score == 0:
        return 0
    if score == 1:
        return 15
    if score == 2:
        return 20
    if score == 3:
        return 28

    return score

def _restore_sofa_from_dimension(score):
    if score is None:
        return None

    if score == 0:
        return 0
    if score == 1:
        return 6
    if score == 2:
        return 10

    return score

def get_patients_by_nra(nratendimento: int):
    """
    Busca pacientes pelo nratendimento filtrando na service.
    """
    try:
        data = nutritional_repository.get_patients_repository()

        # filtro
        filtered = [
            p for p in data if p["id"] == nratendimento
        ]

        return filtered

    except Exception as e:
        logging.error(f"Erro ao buscar pacientes no repositório: {str(e)}")
        raise Exception(
            "Estamos com problemas para consultar pacientes em nossa base, tente novamente mais tarde"
        )
