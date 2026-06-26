"""Service for GET /nutritional/indicators endpoint."""

from decorators.has_permission_decorator import Permission, has_permission
from models.requests.nutritional_indicators_request import NutritionalIndicatorsRequest
from repository.nutritional import nutritional_indicators_repository

_24H = 86400  # seconds


@has_permission(Permission.READ_PRESCRIPTION)
def get_indicators(
    request_data: NutritionalIndicatorsRequest,
    user_permissions: list[Permission],
):
    rows = nutritional_indicators_repository.get_indicators_data(
        setor=request_data.setor,
        ala=request_data.ala,
        start_date=request_data.start_date,
        end_date=request_data.end_date,
    )

    verde = vermelho = cinza = 0

    for row in rows:
        if row.triagem_at is None or row.dtinternacao is None:
            cinza += 1
            continue

        triagem = row.triagem_at
        internacao = row.dtinternacao

        # normalize to naive for delta
        if hasattr(triagem, "tzinfo") and triagem.tzinfo is not None:
            triagem = triagem.replace(tzinfo=None)
        if hasattr(internacao, "tzinfo") and internacao.tzinfo is not None:
            internacao = internacao.replace(tzinfo=None)

        delta = (triagem - internacao).total_seconds()
        if delta <= _24H:
            verde += 1
        else:
            vermelho += 1

    total = verde + vermelho + cinza
    percentual = round(verde / total * 100, 1) if total > 0 else 0.0

    return {
        "percentual": percentual,
        "total": total,
        "verde": verde,
        "vermelho": vermelho,
        "cinza": cinza,
    }
