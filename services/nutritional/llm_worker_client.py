"""Cliente do worker LLM (issue #88) — Passo 2 do fluxo.

Monta o prompt a partir do ``context`` (sem PII) e chama ``POST {LLM_API_URL}/llm/chat``.
Contrato do worker: 200 → ``{"response": "<texto>"}``; erros (400/403/429/502/503/504) →
``{"code", "message", "path"}``.
"""

import json

import requests
from requests.exceptions import JSONDecodeError
from config import Config
from exception.validation_error import ValidationError
from services.nutritional.nutritional_llm_hash import LlmSummaryHashInput
from utils import logger, status
from utils.http_session import session

_TIMEOUT = (3.05, 25)
_CONTEXT_PLACEHOLDER = "{{CONTEXT_JSON}}"

PROMPTS: dict[str, str] = {
    "resumo_clinico": (
        "Você é um nutricionista clínico. Com base exclusivamente no contexto clínico "
        "abaixo (sem dados de identificação do paciente), gere um resumo clínico "
        "nutricional objetivo, em português, destacando estado nutricional, triagens, "
        "diagnóstico GLIM, condutas recentes e alertas relevantes. Não invente dados "
        "ausentes. Este resumo é um apoio à decisão, não substitui a avaliação "
        "profissional.\n\nContexto clínico (JSON):\n" + _CONTEXT_PLACEHOLDER
    ),
}


def build_prompt(hash_input: LlmSummaryHashInput) -> str:
    """Preenche o template do ``report_type`` com o JSON do ``context``."""
    template = PROMPTS.get(hash_input.report_type)
    if template is None:
        raise ValidationError(
            "Tipo de relatório sem prompt configurado",
            "errors.invalidParam",
            status.HTTP_400_BAD_REQUEST,
        )

    context_json = json.dumps(
        hash_input.context, ensure_ascii=False, sort_keys=True
    )
    return template.replace(_CONTEXT_PLACEHOLDER, context_json)


def call_llm(model: str, prompt_text: str, access_token: str) -> str:
    """Chama o worker LLM e retorna o texto do resumo (campo ``response``)."""
    try:
        resp = session.post(
            f"{Config.LLM_API_URL}/llm/chat",
            params={"model": model},
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json={"message": prompt_text},
            timeout=_TIMEOUT,
        )
    except requests.exceptions.Timeout as e:
        logger.backend_logger.error(f"LLM timeout: {e}")
        raise ValidationError(
            "Tempo limite ao gerar o resumo",
            "errors.gatewayTimeout",
            status.HTTP_504_GATEWAY_TIMEOUT,
        )
    except requests.exceptions.RequestException as e:
        logger.backend_logger.error(f"LLM request error: {e}")
        raise ValidationError(
            "Falha ao gerar o resumo",
            "errors.badGateway",
            status.HTTP_502_BAD_GATEWAY,
        )

    if resp.status_code == status.HTTP_200_OK:
        try:
            data: dict = resp.json()
        except JSONDecodeError as e:
            logger.backend_logger.error(f"LLM request error: {e}")
            raise ValidationError(
                 "Falha ao gerar o resumo",
                 "errors.badGateway",
                 status.HTTP_502_BAD_GATEWAY,
             )
        response_text: str = data.get("response")
        if not isinstance(response_text, str):
            logger.backend_logger.error(f"LLM missing/invalid 'response' field: {data}")
            raise ValidationError(
                 "Falha ao gerar o resumo",
                 "errors.badGateway",
                 status.HTTP_502_BAD_GATEWAY,
             )
        return response_text

    logger.backend_logger.error(f"LLM non-200: {resp.status_code} {resp.text}")
    if resp.status_code == status.HTTP_504_GATEWAY_TIMEOUT:
        raise ValidationError(
            "Tempo limite ao gerar o resumo",
            "errors.gatewayTimeout",
            status.HTTP_504_GATEWAY_TIMEOUT,
        )
    raise ValidationError(
        "Falha ao gerar o resumo",
        "errors.badGateway",
        status.HTTP_502_BAD_GATEWAY,
    )
