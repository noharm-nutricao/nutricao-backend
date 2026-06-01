"""Testes da maquinaria do hash do resumo clínico via LLM (issue #88).

Testes puros — não tocam no banco nem precisam de app Flask.
"""

from datetime import datetime
from types import SimpleNamespace
from typing import Any

import pytest

from services.nutritional.nutritional_llm_hash import (
    LlmSummaryHashInput,
    build_clinical_context,
    compute_summary_hash,
)


def _context() -> dict[str, Any]:
    """Contexto clínico SEM PII de exemplo (formato da saída do Step 1)."""
    return {
        "age": 68,
        "gender": "M",
        "weight": 72.5,
        "height": 1.75,
        "weight_date": datetime(2024, 1, 10, 8, 30, 0),
        "dialysis": "N",
        "lactating": False,
        "pregnant": False,
        "id_icd": "A41",
        "screenings": [{"protocolo": "NRS2002", "nrs_total": 4}],
        "glim": [],
        "assessments": [{"conduta": "manter", "created_at": "2024-01-10T08:00:00"}],
        "alerts": [{"tipo": "risco", "severidade": "alta"}],
    }


@pytest.fixture
def hash_input() -> LlmSummaryHashInput:
    return LlmSummaryHashInput(
        nratendimento=123456,
        report_type="resumo_clinico",
        max_assessments=5,
        prompt_version="resumo_clinico",
        model="claude-haiku-4-5",
        max_tokens=800,
        context=_context(),
    )


def test_hash_is_64_hex_chars(hash_input: LlmSummaryHashInput) -> None:
    result = compute_summary_hash(hash_input)
    assert len(result) == 64
    assert all(c in "0123456789abcdef" for c in result)


def test_known_value_regression(hash_input: LlmSummaryHashInput) -> None:
    """Congela o valor para detectar mudanças não intencionais no algoritmo/payload."""
    assert (
        compute_summary_hash(hash_input)
        == "015b4c3d90345fe2815ec60dfba7dcf9a3f975d5ef59647405563287c338dcaf"
    )


def test_key_order_independence(hash_input: LlmSummaryHashInput) -> None:
    """Reordenar as chaves do context não muda o hash (sort_keys=True)."""
    reordered = dict(reversed(list(hash_input.context.items())))
    other = LlmSummaryHashInput(
        nratendimento=hash_input.nratendimento,
        report_type=hash_input.report_type,
        max_assessments=hash_input.max_assessments,
        prompt_version=hash_input.prompt_version,
        model=hash_input.model,
        max_tokens=hash_input.max_tokens,
        context=reordered,
    )
    assert compute_summary_hash(other) == compute_summary_hash(hash_input)


def test_datetime_is_normalized_and_stable(hash_input: LlmSummaryHashInput) -> None:
    """weight_date (datetime) é serializado sem erro e de forma estável."""
    same_instant = dict(hash_input.context)
    same_instant["weight_date"] = datetime(2024, 1, 10, 8, 30, 0)
    other = LlmSummaryHashInput(
        nratendimento=hash_input.nratendimento,
        report_type=hash_input.report_type,
        max_assessments=hash_input.max_assessments,
        prompt_version=hash_input.prompt_version,
        model=hash_input.model,
        max_tokens=hash_input.max_tokens,
        context=same_instant,
    )
    assert compute_summary_hash(other) == compute_summary_hash(hash_input)


@pytest.mark.parametrize(
    "field,value",
    [
        ("nratendimento", 999999),
        ("report_type", "outro_relatorio"),
        ("max_assessments", 10),
        ("prompt_version", "resumo_clinico@2"),
        ("model", "claude-sonnet-4-6"),
        ("max_tokens", 1200),
    ],
)
def test_changing_any_scalar_field_changes_hash(
    hash_input: LlmSummaryHashInput, field: str, value: Any
) -> None:
    baseline = compute_summary_hash(hash_input)
    setattr(hash_input, field, value)
    assert compute_summary_hash(hash_input) != baseline


def test_changing_nested_context_value_changes_hash(
    hash_input: LlmSummaryHashInput,
) -> None:
    baseline = compute_summary_hash(hash_input)
    hash_input.context["age"] = 69
    assert compute_summary_hash(hash_input) != baseline


def test_build_clinical_context_returns_dict_copy() -> None:
    """build_clinical_context materializa o Row._mapping como dict (pass-through)."""
    mapping = {"age": 68, "gender": "M", "screenings": [], "glim": []}
    row = SimpleNamespace(_mapping=mapping)

    result = build_clinical_context(row)

    assert result == mapping
    assert result is not mapping  # cópia, não a mesma referência
