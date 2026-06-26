"""Service layer for GET /nutritional/patients endpoint."""

from datetime import datetime, timezone
import logging
from decorators.has_permission_decorator import Permission, has_permission
from models.enums import SegmentTypeEnum
from models.requests.nutritional_patients_request import NutritionalPatientsRequest
from repository import nutritional_patients_repository
from repository.nutritional import nutritional_repository

log = logging.getLogger(__name__)


def _to_iso_datetime(value):
    if value is None:
        return None
    return value.isoformat()


def _calc_triagem_status(data_internacao, finalizada, dados_incompletos, now):
    if finalizada:
        return "finalizada"
    if data_internacao is None:
        return "em_andamento" if dados_incompletos else "pendente"

    dt = data_internacao
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    overdue = (now - dt).total_seconds() > 86400

    if overdue:
        return "atrasada"
    if dados_incompletos:
        return "em_andamento"
    return "pendente"


def build_patients_payload(rows, now=None):
    if now is None:
        now = datetime.now(timezone.utc)

    patients = []

    for idx, row in enumerate(rows, start=1):
        log.info("Processing patient idx=%s | id=%s", idx, row.id)

        protocolo = "MNUTRIC" if row.tp_segmento == SegmentTypeEnum.ICU.value else "NRS2002"

        idade = _calculate_age(row.dtnascimento, now) if row.dtnascimento else None
        if idade is None:
            log.info("Missing birthdate for patient id=%s", row.id)

        dias = _calculate_days(row.dtinternacao, now) if row.dtinternacao else None
        if dias is None:
            log.info("Missing admission date for patient id=%s", row.id)

        imc = _calculate_imc(row.peso, row.altura)
        if imc is None:
            log.info(
                "IMC not calculated for patient id=%s | peso=%s | altura=%s",
                row.id,
                row.peso,
                row.altura,
            )

        haval = round(row.haval, 1) if row.haval is not None else None
        d7 = bool(row.d7) if row.d7 is not None else False
        sev = row.sev if row.sev else "bx"
        freq_horas = row.freq_horas
        glim_diag = row.glim_diag if row.glim_diag else None
        glim_fen = row.glim_fen if row.glim_fen else []
        glim_etiol = row.glim_etiol if row.glim_etiol else []

        campo1 = _build_campo1(protocolo, row)
        if protocolo == "NRS2002":
            nrs = row.nrs_data or {}
            dados_incompletos = bool(campo1 and nrs.get("nrs_nut") is None)
        else:
            dados_incompletos = bool(campo1 and campo1.get("dados_incompletos"))
        finalizada = row.triagem_finalizada_at is not None
        triagem_at = _to_iso_datetime(row.triagem_finalizada_at)

        patients.append(
            {
                "id": row.id,
                "leito": row.leito,
                "ala": row.ala,
                "fksetor": row.fksetor,
                "nome_setor": row.nome_setor,
                "protocolo": protocolo,
                "idade": idade,
                "dias": dias,
                "peso": row.peso,
                "imc": imc,
                "dieta": None,
                "npo": None,
                "alergia": None,
                "al_ok": True,
                "campo1": campo1,
                "glim_diag": glim_diag,
                "glim_fen": glim_fen,
                "glim_etiol": glim_etiol,
                "inst": row.inst if row.inst else [],
                "conduta": row.conduta,
                "haval": haval,
                "d7": d7,
                "pri": idx,
                "sev": sev,
                "freq_horas": freq_horas,
                "hist": row.hist if row.hist else [],
                "data_internacao": _to_iso_datetime(row.dtinternacao),
                "triagem_at": triagem_at,
                "triagem_status": _calc_triagem_status(
                    data_internacao=row.dtinternacao,
                    finalizada=finalizada,
                    dados_incompletos=dados_incompletos,
                    now=now,
                ),
            }
        )

    return patients


@has_permission(Permission.READ_PRESCRIPTION)
def get_patients(request_data: NutritionalPatientsRequest):
    """Return active admissions with basic patient data for the nutrition module."""

    rows = nutritional_patients_repository.get_patients(
        setor=request_data.setor,
        ala=request_data.ala,
    )

    log.info("Repository returned %s patients", len(rows))

    patients = build_patients_payload(rows=rows)

    log.info("Finished get_patients | total_processed=%s", len(patients))

    return patients


def _calculate_age(birthdate, now):
    """Calculate age in complete years from birthdate."""
    if birthdate is None:
        return None

    # Remove timezone info for comparison if needed
    bd = birthdate
    today = now

    age = today.year - bd.year
    if (today.month, today.day) < (bd.month, bd.day):
        age -= 1

    return age


def _calculate_days(admission_date, now):
    """Calculate days of admission from admission date."""
    if admission_date is None:
        return None

    # Remove timezone info for comparison if needed
    delta = now.replace(tzinfo=None) - admission_date.replace(tzinfo=None)
    return delta.days


def _calculate_imc(peso, altura):
    """Calculate BMI: peso in kg, altura in cm.

    Returns:
        float rounded to 1 decimal, or None if data is missing.
    """
    if peso and altura and altura > 0:
        altura_m = altura / 100.0
        return round(peso / (altura_m**2), 1)
    return None


def _build_campo1(protocolo, row):
    """Build campo1 dict from the latest screening scores.

    Returns None if no score has been calculated yet for this admission.
    For MNUTRIC patients, NRS scores are included when available.
    """
    if not row:
        return None
    nrs = row.nrs_data or {}
    mn = row.mnutric_data or {}
    nrs_dict = None
    if nrs and nrs.get("nrs_total") is not None:
        nrs_nut = nrs.get("nrs_nut")
        nrs_dict = {
            "nrs_total": nrs["nrs_total"],
            "nrs_dims": {
                "nut": nrs_nut if nrs_nut is not None else 0,
                "doenca": nrs.get("nrs_doenca") or 0,
                "idade": nrs.get("nrs_idade") or 0,
            },
        }
    if protocolo == "NRS2002":
        return nrs_dict

    if protocolo == "MNUTRIC":
        if not mn and not nrs_dict:
            return None
        if not mn and nrs_dict:
            return nrs_dict

        apache_manual = mn.get("mn_apache_manual") or False
        sofa_manual = mn.get("mn_sofa_manual") or False
        dados_incompletos = not apache_manual or not sofa_manual

        if dados_incompletos:
            dados_incompletos_dict: dict = {
                "dados_incompletos": True,
                "mn_dims": {
                    "idade": mn.get("mn_idade") or 0,
                    "apache": None,
                    "sofa": None,
                    "comor": mn.get("mn_comor") or 0,
                    "dias": mn.get("mn_dias") or 0,
                },
            }
            if nrs_dict:
                return dados_incompletos_dict | nrs_dict
            return dados_incompletos_dict
        result = {
            "mnutric_total": mn["mn_total"],
            "mn_dims": {
                "idade": mn.get("mn_idade") or 0,
                "apache": mn.get("mn_apache") or 0,
                "sofa": mn.get("mn_sofa") or 0,
                "comor": mn.get("mn_comor") or 0,
                "dias": mn.get("mn_dias") or 0,
            },
        }
        if nrs_dict:
            return result | nrs_dict
        return result

    return None


def _build_inst(nratendimento):
    alerts = nutritional_repository.get_active_lab_alerts(nratendimento)
    return [
        {"t": alert.tipo, "sev": alert.severidade, "d": alert.descricao}
        for alert in alerts
    ]