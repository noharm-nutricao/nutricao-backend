"""Request model for GET /nutritional/patients endpoint."""

from typing import Optional

from pydantic import BaseModel


class NutritionalPatientsRequest(BaseModel):
    """Query parameters for the nutritional patients listing."""

    setor: Optional[int] = None
    ala: Optional[str] = None

