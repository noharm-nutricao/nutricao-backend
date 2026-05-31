"""Request model for POST /nutritional/patients/{nratendimento}/llm-summary."""

from pydantic import BaseModel, Field

MAX_ASSESSMENTS_DEFAULT = 5
MAX_ASSESSMENTS_CAP = 10


class NutritionalLlmSummaryRequest(BaseModel):
    """Body for the LLM clinical-summary endpoint.

    ``max_assessments`` is the number of most-recent assessments to include in
    the clinical context. Defaults to 5 and is capped at 10 (issue #88).
    """

    max_assessments: int = Field(
        default=MAX_ASSESSMENTS_DEFAULT,
        ge=1,
        le=MAX_ASSESSMENTS_CAP,
    )
