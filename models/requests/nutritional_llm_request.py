"""Request model for POST /nutritional/patients/{nratendimento}/llm-summary."""

from enum import Enum

from pydantic import BaseModel, Field

MAX_ASSESSMENTS_DEFAULT = 5
MAX_ASSESSMENTS_CAP = 10

MAX_TOKENS_DEFAULT = 800
MAX_TOKENS_CAP = 4000


class ReportType(str, Enum):
    """Supported LLM report types. PoC has a single one; extensible later."""

    RESUMO_CLINICO = "resumo_clinico"


class LlmModel(str, Enum):
    """Supported LLM models. Anything outside this set is rejected (400)."""

    ANTHROPIC = "ANTHROPIC"
    GPT = "GPT"
    AMAZON_LITE = "AMAZON_LITE"
    MAGISTRAL = "MAGISTRAL"


class NutritionalLlmSummaryRequest(BaseModel):
    """Body for the LLM clinical-summary endpoint.

    ``report_type`` selects which prompt to use (default ``resumo_clinico``).
    ``max_assessments`` is the number of most-recent assessments to include in
    the clinical context. Defaults to 5 and is capped at 10 (issue #88).
    ``model`` is optional and defaults to ``ANTHROPIC``; an unsupported value is
    rejected by Pydantic on the edge (400).
    ``max_tokens`` bounds the LLM output size; it feeds the cache hash and
    defaults to 800.
    """

    report_type: ReportType = ReportType.RESUMO_CLINICO
    max_assessments: int = Field(
        default=MAX_ASSESSMENTS_DEFAULT,
        ge=1,
        le=MAX_ASSESSMENTS_CAP,
    )
    model: LlmModel = LlmModel.ANTHROPIC
    max_tokens: int = Field(
        default=MAX_TOKENS_DEFAULT,
        ge=1,
        le=MAX_TOKENS_CAP,
    )
