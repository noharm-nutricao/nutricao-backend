"""Cálculo do hash do resumo clínico via LLM (issue #88).

O hash é, na versão síncrona, a chave de cache e a chave de idempotência/dedup do resumo.
Tudo que muda o resultado do LLM entra no hash (doc §3.1): ao mudar a versão do prompt, o
modelo, o ``max_tokens`` ou o contexto do paciente, o hash muda e o cache se invalida sozinho.

Lógica pura — sem dependência de banco nem de Flask. ``Row`` é importado apenas para tipagem.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Row


@dataclass
class LlmSummaryHashInput:
    """Entradas que compõem o payload canônico do hash (doc §3.1).

    ``context`` é o estado do paciente, SEM PII — a saída do Step 1
    (``get_clinical_context``) já convertida para dict via :func:`build_clinical_context`.
    """

    nratendimento: int
    report_type: str
    max_assessments: int
    prompt_version: str
    model: str
    max_tokens: int
    context: dict[str, Any]


def build_clinical_context(row: Row) -> dict[str, Any]:
    """Converte o ``Row`` do Step 1 no dict de ``context`` (pass-through).

    O whitelist de colunas já é garantido no SQL de ``get_clinical_context``; aqui apenas
    materializamos o ``Row`` como dict. Assume ``row`` não-nulo (o tratamento de ``None``/404
    pertence ao serviço).
    """

    return dict(row._mapping)


def _json_default(o: object) -> str:
    """Normaliza valores não serializáveis para a serialização canônica.

    ``datetime`` (ex.: ``weight_date`` do contexto) vira ISO 8601. ``Decimal`` é tratado
    defensivamente como string. Qualquer outro tipo levanta ``TypeError``.
    """

    if isinstance(o, datetime):
        return o.isoformat()
    if isinstance(o, Decimal):
        return str(o)
    raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")


def compute_summary_hash(hash_input: LlmSummaryHashInput) -> str:
    """Calcula o SHA-256 (64 hex chars) do payload canônico (doc §3.2).

    ``sort_keys=True`` garante ordenação determinística em todos os níveis (inclusive dentro de
    ``context``), de modo que a ordem de construção dos dicts não altera o hash.
    """

    payload: dict[str, Any] = {
        "nratendimento": hash_input.nratendimento,
        "report_type": hash_input.report_type,
        "max_assessments": hash_input.max_assessments,
        "prompt_version": hash_input.prompt_version,
        "model": hash_input.model,
        "max_tokens": hash_input.max_tokens,
        "context": hash_input.context,
    }

    canonical: str = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=_json_default,
    )

    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
