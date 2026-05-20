from datetime import datetime

from sqlalchemy import text

from decorators.has_permission_decorator import has_permission
from exception.validation_error import ValidationError
from models.enums import SegmentTypeEnum
from models.main import User, db
from models.nutritional import NutritionalTriagem, NutritionalScreening
from models.prescription import Patient
from security.permission import Permission
from utils import status
from utils.dateutils import now_sp, today_sp


_MNUTRIC_AGE_THRESHOLDS = [(75, 2), (60, 1)]
_MNUTRIC_APACHE_THRESHOLDS = [(24, 2), (15, 1)]
_MNUTRIC_SOFA_THRESHOLDS = [(10, 2), (6, 1)]
_MNUTRIC_DAYS_THRESHOLDS = [(4, 1)]


def _mnutric_score_idade(age):
    for threshold, score in _MNUTRIC_AGE_THRESHOLDS:
        if age >= threshold:
            return score
    return 0


def _mnutric_score_apache(apache):
    for threshold, score in _MNUTRIC_APACHE_THRESHOLDS:
        if apache >= threshold:
            return score
    return 0


def _mnutric_score_sofa(sofa):
    for threshold, score in _MNUTRIC_SOFA_THRESHOLDS:
        if sofa >= threshold:
            return score
    return 0


def _mnutric_score_dias(dias):
    for threshold, score in _MNUTRIC_DAYS_THRESHOLDS:
        if dias >= threshold:
            return score
    return 0


def _mnutric_score_comor(id_icd):
    return 1 if id_icd else 0


def _calculate_age(birthdate):
    if birthdate is None:
        return 0
    today = today_sp()
    bd = birthdate if hasattr(birthdate, "year") else birthdate.date()
    return today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day))


def _calculate_days(admission_date):
    if admission_date is None:
        return 0

    today = today_sp()

    # garante que é date
    if isinstance(admission_date, datetime):
        ad = admission_date.date()
    else:
        ad = admission_date

    # opcional (segurança extra)
    if isinstance(today, datetime):
        today = today.date()

    return (today - ad).days


@has_permission(Permission.WRITE_NUTRITIONAL)
def update_nrs_nut(nratendimento, request_data, user_context: User):
    patient = (
        db.session.query(Patient)
        .filter(Patient.admissionNumber == nratendimento)
        .first()
    )

    if patient is None:
        raise ValidationError(
            "Paciente não encontrado",
            "errors.notFound",
            status.HTTP_404_NOT_FOUND,
        )

    tp_segmento = _get_segment_type(nratendimento)

    if tp_segmento != SegmentTypeEnum.ICU.value:
        raise ValidationError(
            "Paciente não é de UTI — endpoint exclusivo para protocolo MNUTRIC",
            "errors.businessRule",
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    triagem = (
        db.session.query(NutritionalScreening)
        .filter(NutritionalScreening.nratendimento == nratendimento)
        .order_by(NutritionalScreening.created_at.desc())
        .first()
    )

    now = now_sp()

    if triagem is None:
        triagem = NutritionalScreening()
        triagem.nratendimento = nratendimento
        triagem.created_at = now
        triagem.created_by = user_context.id
        triagem.protocolo = "MNUTRIC"
        db.session.add(triagem)

    age = _calculate_age(patient.birthdate)
    dias = _calculate_days(patient.admissionDate)

    mn_idade = _mnutric_score_idade(age)
    mn_apache = _mnutric_score_apache(request_data.apache_ii)
    mn_sofa = _mnutric_score_sofa(request_data.sofa)
    mn_comor = _mnutric_score_comor(patient.id_icd)
    mn_dias = _mnutric_score_dias(dias)

    triagem.mn_apache = mn_apache
    triagem.mn_sofa = mn_sofa
    triagem.mn_apache_manual = True
    triagem.mn_sofa_manual = True
    triagem.updated_at = now
    triagem.updated_by = user_context.id

    mnutric_total = mn_idade + mn_apache + mn_sofa + mn_comor + mn_dias
    triagem.mnutric_total = mnutric_total

    nrs_nut = triagem.nrs_nut if triagem.nrs_nut is not None else 0
    nrs_doenca = triagem.nrs_doenca if triagem.nrs_doenca is not None else 0
    nrs_idade_score = 1 if age >= 70 else 0
    nrs_total = nrs_nut + nrs_doenca + nrs_idade_score

    nrs_completo = triagem.nrs_completo if triagem.nrs_completo is not None else False

    if mnutric_total >= 5:
        classificacao = "cr"
    elif mnutric_total >= 3:
        classificacao = "md"
    else:
        classificacao = "bx"

    triagem.classificacao = classificacao

    db.session.flush()

    return {
        "campo1": {
            "protocolo": "MNUTRIC",
            "mnutric_total": mnutric_total,
            "mn_dims": {
                "idade": mn_idade,
                "apache": mn_apache,
                "sofa": mn_sofa,
                "comor": mn_comor,
                "dias": mn_dias,
            },
            "mn_apache_manual": True,
            "mn_sofa_manual": True,
            "dados_incompletos": False,
            "nrs_total": nrs_total,
            "nrs_dims": {
                "nut": nrs_nut,
                "doenca": nrs_doenca,
                "idade": nrs_idade_score,
            },
            "nrs_completo": nrs_completo,
            "classificacao": classificacao,
        }
    }


def _get_segment_type(nratendimento):
    schema = (
        db.session.connection()
        .get_execution_options()
        .get("schema_translate_map", {})
        .get(None) or "demo"
    )
    result = db.session.execute(
        text(
            f"""
            SELECT seg.tp_segmento
            FROM "{schema}".pessoa p
            JOIN "{schema}".segmentosetor ss ON ss.fksetor = p.fksetor
            JOIN "{schema}".segmento seg ON seg.idsegmento = ss.idsegmento
            WHERE p.nratendimento = :nratendimento
            LIMIT 1
            """
        ),
        {"nratendimento": nratendimento},
    ).fetchone()

    if result is None:
        return None

    return result[0]



