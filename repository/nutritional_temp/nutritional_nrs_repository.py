from typing import Optional

from sqlalchemy import and_

from models.appendix import Department
from models.main import db
from models.prescription import Prescription
from models.temp_nutritional import NutricionalNrs, NutricionalTriagem
from services.temp_nutritional.nutritional_dtos import NrsScoreDTO


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
