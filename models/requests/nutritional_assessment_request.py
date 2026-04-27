from typing import Optional
from pydantic import BaseModel, field_validator


class NutritionalAssessmentRequest(BaseModel):
    conduta: str
    prox_visita: str
    ingestao: Optional[int] = None
    meta_kcal: Optional[int] = None
    meta_prot: Optional[int] = None

    @field_validator("conduta")
    @classmethod
    def validate_conduta(cls, value):
        if not value.strip():
            raise ValueError("conduta obrigatoria")
        return value

    @field_validator("prox_visita")
    @classmethod
    def validate_prox_visita(cls, value):
        allowed = {"24h", "48h", "semanal", "D7", "rotina"}

        if value not in allowed:
            raise ValueError("prox_visita invalido")

        return value

    @field_validator("ingestao")
    @classmethod
    def validate_ingestao(cls, value):
        if value is not None and not (0 <= value <= 100):
            raise ValueError("ingestao deve ser entre 0 e 100")
        return value

