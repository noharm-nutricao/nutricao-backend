"""Serviço síncrono do resumo clínico via LLM (issue #88, PoC).

Esta etapa orquestra o Step 1 (contexto sem PII) e o cálculo do hash (chave de cache +
idempotência, §3). O restante (cache/dedup → chamada ao LLM → persistência → resposta) será
implementado a seguir.
"""

from typing import Literal, Optional

from sqlalchemy import Row

from decorators.has_permission_decorator import has_permission
from exception.validation_error import ValidationError
from models.requests.nutritional_llm_request import NutritionalLlmSummaryRequest
from repository.nutritional import nutritional_llm_repository
from security.permission import Permission
from services.nutritional.nutritional_llm_hash import (
    LlmSummaryHashInput,
    build_clinical_context,
    compute_summary_hash,
)
from utils import status


def build_hash_input(
    nratendimento: int, request_data: NutritionalLlmSummaryRequest
) -> LlmSummaryHashInput:
    """Busca o contexto (Step 1) e monta o payload do hash (§3.1).

    No fluxo síncrono não há worker: ``prompt_version`` é igual ao ``report_type``. Levanta
    ``ValidationError`` 404 quando o atendimento não existe.
    """

    row: Optional[Row] = nutritional_llm_repository.get_clinical_context(
        nratendimento, request_data.max_assessments
    )
    if row is None:
        raise ValidationError(
            "Atendimento não encontrado",
            "errors.invalidParam",
            status.HTTP_404_NOT_FOUND,
        )

    context: dict = build_clinical_context(row)
    report_type: str = request_data.report_type.value

    return LlmSummaryHashInput(
        nratendimento=nratendimento,
        report_type=report_type,
        max_assessments=request_data.max_assessments,
        prompt_version=report_type,  # síncrono: prompt_version == report_type
        model=request_data.model.value,
        max_tokens=request_data.max_tokens,
        context=context,
    )


@has_permission(Permission.READ_PRESCRIPTION)
def generate_summary(
    nratendimento: int,
    request_data: NutritionalLlmSummaryRequest,
    user_context,
) -> dict:
    """Gera (ou devolve do cache) o resumo clínico de forma síncrona.

    Retorna ``{summary, generated_at, tokens_used, model}``. Levanta ``ValidationError`` com
    404 (atendimento inexistente), 502 (erro do LLM) e 504 (timeout do LLM).
    """

    hash_input : Optional[LlmSummaryHashInput] = build_hash_input(nratendimento, request_data)
    context_hash: str = compute_summary_hash(hash_input)

    cached = nutritional_llm_repository.get_cached_summary(context_hash)
    if cached is not None:
        generated_at = cached.processed_at or cached.created_at
        return {
            "summary": cached.summary,
            "generated_at": generated_at.isoformat() if generated_at else None,
            "tokens_used": cached.tokens_used,
            "model": cached.model,
        }

    nutritional_llm_repository.insert_pending_job(
        context_hash=context_hash,
        nratendimento=hash_input.nratendimento,
        report_type=hash_input.report_type,
        max_assessments=hash_input.max_assessments,
        prompt_version=hash_input.prompt_version,
        model=hash_input.model,
    )

    # TODO próxima etapa (fora deste prompt): montar prompt, chamar o LLM (502/504),
    # UPDATE status=done + summary/tokens, e devolver {summary, generated_at, tokens_used, model}.
    raise NotImplementedError
