"""Nutritional clinical and prescription alert severity calculation."""

import logging

from services.nutritional.nutritional_text_utils import normalize_text


CLIN_CASES = {
    "vomito": {"severidade": "al", "observacao": "Vômitos registrados"},
    "diarreia": {"severidade": "al", "observacao": "Diarreia registrada"},
    "jejum": {"severidade": "cr", "observacao": "Jejum prolongado"},
}


def calculate_clin_severity(nratendimento: int, idevolucao: int, sintomas: list[str]) -> None:
    """
    Calcula a severidade do alerta clínico a partir dos sintomas da evolução.
    Para cada sintoma, normaliza o texto e mapeia com os casos clínicos.
    Chama generate_alert() com a severidade e tipo 'clin'.
    """
    for sintoma in sintomas:
        normalized = normalize_text(sintoma)

        for key, case in CLIN_CASES.items():
            if key in normalized:
                logging.info(
                    f"Alerta clin detectado: {key} | nratendimento={nratendimento} | idevolucao={idevolucao}"
                )
                # generate_alert será implementado no próximo commit
                # generate_alert(
                #     severity=case["severidade"],
                #     nratendimento=nratendimento,
                #     type="clin",
                #     trigger_origin_id=idevolucao,
                #     observation=case["observacao"],
                # )
                break