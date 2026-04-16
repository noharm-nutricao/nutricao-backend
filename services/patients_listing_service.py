"""Service: patient listing with nutritional screening (campo1) data."""

from decorators.has_permission_decorator import Permission, has_permission
from repository import triagem_repository


@has_permission(Permission.READ_PRESCRIPTION)
def get_patients_listing(
    id_segment: int = None,
    id_department: int = None,
    user_permissions: list = None,
):
    """Return active patients with their nutritional screening (campo1) data.

    Ordered by triagem.pri ASC (highest priority first), NULLS LAST, then
    admission number ASC for deterministic tie-breaking.
    """
    rows = triagem_repository.get_patients_with_triagem(
        id_segment=id_segment,
        id_department=id_department,
    )

    result = []
    for patient, triagem, ala in rows:
        campo1 = None
        if triagem is not None:
            campo1 = {
                "protocolo": triagem.protocolo,
                "mnutric_total": triagem.mnutric_total,
                "mn_dims": triagem.mn_dims,
                "mn_apache_manual": triagem.mn_apache_manual or False,
                "mn_sofa_manual": triagem.mn_sofa_manual or False,
                "dados_incompletos": triagem.dados_incompletos or False,
                "nrs_total": triagem.nrs_total,
                "nrs_dims": triagem.nrs_dims,
                "nrs_completo": triagem.nrs_completo or False,
                "classificacao": triagem.classificacao,
                "calculado_at": (
                    triagem.calculado_at.isoformat() if triagem.calculado_at else None
                ),
            }

        result.append(
            {
                "id": patient.admissionNumber,
                "leito": patient.bed,
                "ala": ala,
                "protocolo": triagem.protocolo if triagem is not None else None,
                "campo1": campo1,
                "sev": triagem.sev if triagem is not None else None,
                "pri": triagem.pri if triagem is not None else None,
                "haval": triagem.haval if triagem is not None else None,
                "d7": (triagem.d7 or False) if triagem is not None else False,
            }
        )

    return result
