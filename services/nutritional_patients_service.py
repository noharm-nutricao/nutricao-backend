"""Service layer for GET /nutritional/patients endpoint."""

from datetime import datetime, timezone

from decorators.has_permission_decorator import Permission, has_permission
from models.enums import SegmentTypeEnum
from models.requests.nutritional_patients_request import NutritionalPatientsRequest
from repository import nutritional_patients_repository


@has_permission(Permission.READ_PRESCRIPTION)
def get_patients(request_data: NutritionalPatientsRequest):
    """Return active admissions with basic patient data for the nutrition module.

    Business logic:
    - protocolo derived from tp_segmento (ICU=3 -> MNUTRIC, else -> NRS2002)
    - idade calculated from dtnascimento
    - dias calculated from dtinternacao
    - imc calculated from peso (kg) and altura (cm)
    - campo1 is null in this US (populated in US-BE-07)
    - hist is empty array in this US
    - Patient name is NOT returned (LGPD)
    """

    rows = nutritional_patients_repository.get_patients(
        setor=request_data.setor,
        ala=request_data.ala,
    )

    patients = []
    now = datetime.now(timezone.utc)

    for idx, row in enumerate(rows, start=1):
        # Derive protocolo from segment type
        protocolo = "MNUTRIC" if row.tp_segmento == SegmentTypeEnum.ICU.value else "NRS2002"

        # Calculate idade (age in complete years)
        idade = _calculate_age(row.dtnascimento, now) if row.dtnascimento else None

        # Calculate dias (days of admission)
        dias = _calculate_days(row.dtinternacao, now) if row.dtinternacao else None

        # Calculate IMC (BMI): peso in kg, altura in cm
        imc = _calculate_imc(row.peso, row.altura)

        # haval: round to 1 decimal place if not None
        haval = round(row.haval, 1) if row.haval is not None else None

        # d7: ensure boolean
        d7 = bool(row.d7) if row.d7 is not None else False

        # sev: default to "bx" in Sprint 0
        sev = row.sev if row.sev else "bx"

        # GLIM fields
        glim_diag = row.glim_diag if row.glim_diag else None
        glim_fen = row.glim_fen if row.glim_fen else []
        glim_etiol = row.glim_etiol if row.glim_etiol else []

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
                "dieta": None,  # from demo.presmed - not implemented in this US
                "npo": None,  # from demo.presmed - not implemented in this US
                "alergia": None,  # from demo.pessoa - not implemented in this US
                "al_ok": True,  # default: true when alergia is null
                "campo1": None,  # null in this US (populated in US-BE-07)
                "glim_diag": glim_diag,
                "glim_fen": glim_fen,
                "glim_etiol": glim_etiol,
                "inst": [],  # from demo.nutricional_alerta - empty for now
                "conduta": row.conduta,
                "haval": haval,
                "d7": d7,
                "pri": idx,  # position in the priority queue
                "sev": sev,
                "hist": [],  # empty in this US
            }
        )

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

