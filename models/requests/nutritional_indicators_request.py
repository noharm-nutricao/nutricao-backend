"""Request model for GET /nutritional/indicators endpoint."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class NutritionalIndicatorsRequest(BaseModel):
    setor: Optional[int] = None
    ala: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
