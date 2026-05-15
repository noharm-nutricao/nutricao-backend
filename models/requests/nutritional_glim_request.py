from typing import Optional

from pydantic import BaseModel, computed_field, field_validator


FENOTIPOS = {"perda_peso", "imc_baixo", "reducao_mm"}
ETIOLOGIAS = {
    "ingestao_reduzida",
    "ma_absorcao",
    "inflamacao_aguda",
    "inflamacao_cronica",
}

DIAGNOSTICO_TO_DB = {
    "sem_desnutricao": "nd",
    "desnutricao_leve_moderada": "mod",
    "desnutricao_grave": "grave",
    "nd": "nd",
    "mod": "mod",
    "grave": "grave",
}

DIAGNOSTICO_DB_TO_API = {
    "nd": "sem_desnutricao",
    "mod": "desnutricao_leve_moderada",
    "grave": "desnutricao_grave",
}


def diagnostico_to_api(value: str) -> str:
    return DIAGNOSTICO_DB_TO_API.get(value, value)


class NutritionalGlimRequest(BaseModel):
    fenotipos: Optional[list[str]] = None
    etiologias: Optional[list[str]] = None
    diagnostico: str
    observacao: Optional[str] = None

    @field_validator("fenotipos")
    @classmethod
    def validate_fenotipos(cls, value):
        if value is None:
            return value

        invalid = [item for item in value if item not in FENOTIPOS]
        if invalid:
            raise ValueError("fenotipos invalidos")

        return value

    @field_validator("etiologias")
    @classmethod
    def validate_etiologias(cls, value):
        if value is None:
            return value

        invalid = [item for item in value if item not in ETIOLOGIAS]
        if invalid:
            raise ValueError("etiologias invalidas")

        return value

    @field_validator("diagnostico")
    @classmethod
    def validate_diagnostico(cls, value):
        if value not in DIAGNOSTICO_TO_DB:
            raise ValueError("diagnostico invalido")

        return value

    @computed_field
    @property
    def diagnostico_db(self) -> str:
        return DIAGNOSTICO_TO_DB[self.diagnostico]
