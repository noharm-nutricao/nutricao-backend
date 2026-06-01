"""Serviço síncrono do resumo clínico via LLM (issue #88, PoC).

Apenas a assinatura nesta etapa — o corpo (contexto → hash → cache/dedup → chamada ao LLM →
persistência → resposta) será implementado a seguir.
"""

from decorators.has_permission_decorator import has_permission
from models.requests.nutritional_llm_request import NutritionalLlmSummaryRequest
from security.permission import Permission


@has_permission(Permission.READ_PRESCRIPTION)
def generate_summary(
    nratendimento: int,
    request_data: NutritionalLlmSummaryRequest,
    user_context,
) -> dict:
    """Gera (ou devolve do cache) o resumo clínico de forma síncrona.

    Retorna ``{summary, generated_at, tokens_used, model}``. Levanta ``ValidationError`` com
    404 (atendimento inexistente), 502 (erro do LLM) e 504 (timeout do LLM). Corpo na próxima
    etapa.
    """

    raise NotImplementedError
