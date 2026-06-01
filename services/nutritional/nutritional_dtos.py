from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class NrsScoreDTO:
    id: int
    nrs_nut: Optional[int]
    nrs_doenca: int
    nrs_idade: int
    nrs_total: int
    classificacao: str
    nrs_completo: bool
    nrs_ref_at: datetime
    calculado_at: datetime


@dataclass
class CidMappings:
    overrides: dict
    chapters: dict
