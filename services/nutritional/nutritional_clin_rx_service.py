
import logging

from repository.nutritional import nutritional_alert_repository
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


def nutritional_alert_engine() -> None:
    evol_pending_alerts = nutritional_alert_repository.get_evol_pending_aux_alerts()
    for pending_alert in evol_pending_alerts:
        calculate_clin_severity(pending_alert.nratendimento, pending_alert.sintomas, pending_alert.fkevolucao)
        nutritional_alert_repository.recon_pending_aux_alert(pending_alert.id)

    pres_pending_alerts = nutritional_alert_repository.get_pres_pending_aux_alerts()
    for pending_alert in pres_pending_alerts:
        calculate_rx_severity(pending_alert.nratendimento, pending_alert.complemento, pending_alert.fkpresmed)
        nutritional_alert_repository.recon_pending_aux_alert(pending_alert.id)


def calculate_clin_severity(nratendimento: int, symptoms: list[str], fkevolucao: int) -> None:
    """
    Calcula a severidade do alerta clínico a partir dos sintomas da evolução.
    """
    registered_cases= []
    for symptom in symptoms:
        normalized_symptom = normalize_text(symptom)
        for key, case in CLIN_CASES.items():
            if key in normalized_symptom:
                if key not in registered_cases:
                    logging.info(f"Alerta clin detectado: {key} | nratendimento={nratendimento}")
                    registered_cases.append(case)
                    generate_alert(
                        severity=case["severidade"],
                        nratendimento=nratendimento,
                        alert_type="clin",
                        observation=case["observacao"],
                        fkevolucao=fkevolucao,
                        fkpresmed=None,
                    )
                break


def calculate_rx_severity(nratendimento: int, itens_prescricao: list[str], fkpresmed: int) -> None:
    """
    Calcula a severidade do alerta de prescrição dietética.
    """
    registered_cases = []
    for item in itens_prescricao:
        normalized = normalize_text(item)
        for key, case in RX_CASES.items():
            if key in normalized:
                if key not in registered_cases:
                    registered_cases.append(case)
                    logging.info(f"Alerta rx detectado: {key} | nratendimento={nratendimento}")
                    generate_alert(
                        severity=case["severidade"],
                        nratendimento=nratendimento,
                        alert_type="rx",
                        observation=case["observacao"],
                        fkevolucao=None,
                        fkpresmed=fkpresmed,
                    )
                break

def generate_alert(severity: str, nratendimento: int, alert_type: str, observation: str, fkevolucao: int | None, fkpresmed: int | None) -> None:
    nutritional_alert_repository.generate_alert(
        severity=severity,
        nratendimento=nratendimento,
        alert_type=alert_type,
        observation=observation,
        fkevolucao=fkevolucao,
        fkpresmed=fkpresmed,
    )
