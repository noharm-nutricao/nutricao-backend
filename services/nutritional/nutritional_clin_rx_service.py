
import logging

from services.nutritional.nutritional_text_utils import normalize_text


CLIN_CASES = {
    "vomito": {"severidade": "al", "observacao": "Vômitos registrados"},
    "diarreia": {"severidade": "al", "observacao": "Diarreia registrada"},
    "jejum": {"severidade": "cr", "observacao": "Jejum prolongado"},
}

RX_CASES = {
    "via alimentar": {"severidade": "al", "observacao": "Mudança de via alimentar"},
    "volume": {"severidade": "md", "observacao": "Mudança de volume"},
    "formula": {"severidade": "md", "observacao": "Mudança de fórmula"},
}


def calculate_clin_severity(nratendimento: int, idevolucao: int, sintomas: list[str]) -> None:
    """
    Calcula a severidade do alerta clínico a partir dos sintomas da evolução.
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


def calculate_rx_severity(nratendimento: int, idpresmed: int, itens_prescricao: list[str]) -> None:
    """
    Calcula a severidade do alerta de prescrição dietética.
    """
    for item in itens_prescricao:
        normalized = normalize_text(item)
        for key, case in RX_CASES.items():
            if key in normalized:
                logging.info(
                    f"Alerta rx detectado: {key} | nratendimento={nratendimento} | idpresmed={idpresmed}"
                )
                # generate_alert será implementado no próximo commit
                # generate_alert(
                #     severity=case["severidade"],
                #     nratendimento=nratendimento,
                #     type="rx",
                #     trigger_origin_id=idpresmed,
                #     observation=case["observacao"],
                # )
                break
