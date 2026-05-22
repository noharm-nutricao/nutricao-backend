from functools import lru_cache
from typing import Optional


from flask_sqlalchemy.session import Session
from sqlalchemy import Row, and_

from models.appendix import Department
from models.main import db
from models.prescription import Prescription
from models.nutritional import NutritionalNrs, NutritionalScreening
from models.segment import Segment
from services.nutritional.nutritional_dtos import CidMappings, NrsScoreDTO


def get_nrs_assessment(nratendimento: int) -> Optional[NutritionalNrs]:
    return _get_nrs_assessment(db.session, nratendimento)


def _get_nrs_assessment(
    session: Session, nratendimento: int
) -> Optional[NutritionalNrs]:
    return (
        session.query(NutritionalNrs)
        .filter(NutritionalNrs.nratendimento == nratendimento)
        .order_by(NutritionalNrs.updated_at.desc())
        .first()
    )


def get_or_create_triagem(nratendimento: int) -> NutritionalScreening:
    return _get_or_create_triagem(db.session, nratendimento)


def _get_or_create_triagem(
    session: Session, nratendimento: int
) -> NutritionalScreening:
    triagem: Optional[NutritionalScreening] = (
        session.query(NutritionalScreening)
        .filter(NutritionalScreening.nratendimento == nratendimento)
        .first()
    )
    if triagem:
        return triagem

    triagem = NutritionalScreening(
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
    session.add(triagem)
    session.flush()
    return triagem


def update_triagem(triagem: NutritionalScreening, nrs_score: NrsScoreDTO) -> None:
    _update_triagem(db.session, triagem, nrs_score)
    return None


def _update_triagem(
    session: Session, triagem: NutritionalScreening, nrs_score: NrsScoreDTO
) -> None:
    triagem.nrs_nut = nrs_score.nrs_nut
    triagem.nrs_doenca = nrs_score.nrs_doenca
    triagem.nrs_idade = nrs_score.nrs_idade
    triagem.nrs_total = nrs_score.nrs_total
    triagem.classificacao = nrs_score.classificacao
    triagem.nrs_completo = nrs_score.nrs_completo
    triagem.nrs_ref_at = nrs_score.nrs_ref_at
    triagem.calculado_at = nrs_score.calculado_at

    session.add(triagem)
    session.flush()
    return None


def get_patient_department(nratendimento: int) -> Optional[str]:
    return _get_patient_department(db.session, nratendimento)


def _get_patient_department(session: Session, nratendimento: int) -> Optional[str]:
    row: Row = (
        session.query(Department.name)
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
    return row.name if row else None

def get_patient_segment_type(nratendimento: int) -> Optional[int]:
    return _get_patient_segment_type(db.session, nratendimento)


def _get_patient_segment_type(session: Session, nratendimento: int) -> Optional[int]:
    row: Row = (
        session.query(Segment.type)
        .join(
            Prescription,
            Segment.id == Prescription.idSegment,
        )
        .filter(Prescription.admissionNumber == nratendimento)
        .order_by(Prescription.date.desc())
        .limit(1)
        .first()
    )
    return row.type if row else None

def get_nutricional_cid_override(session: Session) -> list[tuple[str, int]]:
    rows = session.execute(db.text("""
            SELECT prefixo3, score_nrs
            FROM public.nutricional_cid_override
            """)).fetchall()
    return [(row[0], row[1]) for row in rows]


def get_nutricional_cid_gravidade(session: Session) -> list[tuple[str, int]]:
    rows = session.execute(db.text("""
            SELECT prefixo, score_nrs
            FROM public.nutricional_cid_gravidade
            """)).fetchall()
    return [(row[0], row[1]) for row in rows]


def build_cid_mappings(session: Session) -> CidMappings:
    overrides: list = get_nutricional_cid_override(session)
    chapters: list = get_nutricional_cid_gravidade(session)
    overrides: dict = {row[0]: row[1] for row in overrides}
    chapters: dict = {row[0]: row[1] for row in chapters}
    return CidMappings(overrides=overrides, chapters=chapters)


@lru_cache(maxsize=1)
def get_cid_mappings_cached() -> CidMappings:
    return build_cid_mappings(db.session)
