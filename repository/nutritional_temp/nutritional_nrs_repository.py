from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

from requests import Session
from sqlalchemy import and_

from models.appendix import Department
from models.main import db
from models.prescription import Prescription
from models.temp_nutritional import (
    NutricionalCidGravidade,
    NutricionalCidOverride,
    NutricionalNrs,
    NutricionalTriagem,
)
from services.temp_nutritional.nutritional_dtos import CidMappings, NrsScoreDTO


def get_nrs_assessment(nratendimento: int) -> Optional[NutricionalNrs]:
    return (
        db.session.query(NutricionalNrs)
        .filter(NutricionalNrs.nratendimento == nratendimento)
        .order_by(NutricionalNrs.updated_at.desc())
        .first()
    )


def get_or_create_triagem(nratendimento: int) -> NutricionalTriagem:
    triagem: Optional[NutricionalTriagem] = (
        db.session.query(NutricionalTriagem)
        .filter(NutricionalTriagem.nratendimento == nratendimento)
        .first()
    )
    if triagem:
        return triagem

    triagem = NutricionalTriagem(
        nratendimento=nratendimento,
        protocolo="NRS2002",
        nrs_nut=None,
        nrs_doenca=None,
        nrs_idade=None,
        nrs_total=None,
        nrs_completo=False,
        nrs_ref_at=None,
        mn_idade=None,
        mn_apache=None,
        mn_sofa=None,
        mn_comor=None,
        mn_dias=None,
        mn_total=None,
        mn_apache_manual=None,
        mn_sofa_manual=None,
        classificacao=None,
        calculado_at=None,
    )
    db.session.add(triagem)
    db.session.flush()
    return triagem


def update_triagem(triagem: NutricionalTriagem, nrs_score: NrsScoreDTO) -> None:
    triagem.nrs_nut = nrs_score.nrs_nut
    triagem.nrs_doenca = nrs_score.nrs_doenca
    triagem.nrs_idade = nrs_score.nrs_idade
    triagem.nrs_total = nrs_score.nrs_total
    triagem.nrs_completo = nrs_score.nrs_completo
    triagem.nrs_ref_at = nrs_score.nrs_ref_at
    triagem.calculado_at = nrs_score.calculado_at

    db.session.add(triagem)
    db.session.flush()
    return None


def get_patient_department(nratendimento: int) -> Optional[str]:
    row = (
        db.session.query(Department.name)
        .join(
            Prescription,
            and_(
                Department.id == Prescription.idDepartment,
                Department.idHospital == Prescription.idHospital,
            ),
        )
        .filter(Prescription.admissionNumber == nratendimento)
        .order_by(Prescription.date.desc())
        .limit(1)
        .first()
    )
    return row[0] if row else None


def get_nutricional_cid_override(session: Session) -> list[tuple[str, int]]:
    return session.query(
        NutricionalCidOverride.prefixo3,
        NutricionalCidOverride.score_nrs,
    ).all()


def get_nutricional_cid_gravidade(session: Session) -> list[tuple[str, int]]:
    return session.query(
        NutricionalCidGravidade.prefixo,
        NutricionalCidGravidade.score_nrs,
    ).all()


def build_cid_mappings(session: Session) -> CidMappings:
    overrides: list = get_nutricional_cid_override(session)
    chapters: list = get_nutricional_cid_gravidade(session)
    overrides: dict = {row[0]: row[1] for row in overrides}
    chapters: dict = ({row[0]: row[1] for row in chapters},)
    return CidMappings(overrides=overrides, chapters=chapters)


@lru_cache(maxsize=1)
def get_cid_mappings_cached() -> CidMappings:
    return build_cid_mappings(db.session)
