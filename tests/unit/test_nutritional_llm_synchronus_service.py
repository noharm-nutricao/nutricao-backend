"""Testes da orquestração do hash no serviço síncrono (issue #88, §3).

Testes puros — o repositório é mockado, então não tocam no banco.
"""

from datetime import datetime
from types import SimpleNamespace

import pytest

from exception.validation_error import ValidationError
from models.requests.nutritional_llm_request import (
    LlmModel,
    NutritionalLlmSummaryRequest,
    ReportType,
)
from services.nutritional import nutritional_llm_synchronus_service as svc
from services.nutritional.nutritional_llm_hash import (
    LlmSummaryHashInput,
    compute_summary_hash,
)
from utils import status


def _context_mapping() -> dict:
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
def request_data() -> NutritionalLlmSummaryRequest:
    return NutritionalLlmSummaryRequest(
        report_type=ReportType.RESUMO_CLINICO,
        max_assessments=5,
        model=LlmModel.ANTHROPIC,
        max_tokens=800,
    )


@pytest.fixture
def fake_row() -> SimpleNamespace:
    """Imita um SQLAlchemy Row: expõe ``_mapping`` como dict."""
    return SimpleNamespace(_mapping=_context_mapping())


def _patch_context(monkeypatch, return_value) -> None:
    monkeypatch.setattr(
        svc.nutritional_llm_repository,
        "get_clinical_context",
        lambda *args, **kwargs: return_value,
    )


def test_build_hash_input_maps_fields(monkeypatch, request_data, fake_row) -> None:
    _patch_context(monkeypatch, fake_row)

    result = svc.build_hash_input(123456, request_data)

    assert isinstance(result, LlmSummaryHashInput)
    assert result.nratendimento == 123456
    assert result.report_type == "resumo_clinico"
    assert result.prompt_version == "resumo_clinico"  # síncrono: igual ao report_type
    assert result.max_assessments == 5
    assert result.model == "ANTHROPIC"  # value do enum, não str(enum)
    assert result.max_tokens == 800
    assert result.context == _context_mapping()


def test_build_hash_input_passes_max_assessments_to_repo(
    monkeypatch, request_data, fake_row
) -> None:
    captured = {}

    def _capture(admission_number, max_assessments, *args, **kwargs):
        captured["admission_number"] = admission_number
        captured["max_assessments"] = max_assessments
        return fake_row

    monkeypatch.setattr(
        svc.nutritional_llm_repository, "get_clinical_context", _capture
    )

    svc.build_hash_input(777, request_data)

    assert captured == {"admission_number": 777, "max_assessments": 5}


def test_build_hash_input_raises_404_when_context_missing(
    monkeypatch, request_data
) -> None:
    _patch_context(monkeypatch, None)

    with pytest.raises(ValidationError) as exc_info:
        svc.build_hash_input(123456, request_data)

    assert exc_info.value.httpStatus == status.HTTP_404_NOT_FOUND


def test_hash_is_deterministic_64_hex(monkeypatch, request_data, fake_row) -> None:
    _patch_context(monkeypatch, fake_row)

    h1 = compute_summary_hash(svc.build_hash_input(123456, request_data))
    h2 = compute_summary_hash(svc.build_hash_input(123456, request_data))

    assert h1 == h2
    assert len(h1) == 64
    assert all(c in "0123456789abcdef" for c in h1)


@pytest.mark.parametrize(
    "field,value",
    [
        ("model", LlmModel.GPT),
        ("max_tokens", 1200),
        ("max_assessments", 10),
    ],
)
def test_changing_request_changes_hash(
    monkeypatch, request_data, fake_row, field, value
) -> None:
    _patch_context(monkeypatch, fake_row)
    baseline = compute_summary_hash(svc.build_hash_input(123456, request_data))

    setattr(request_data, field, value)
    changed = compute_summary_hash(svc.build_hash_input(123456, request_data))

    assert changed != baseline
