"""Repository for GET /nutritional/indicators query."""

from sqlalchemy import func, or_

from models.appendix import Department, SegmentDepartment
from models.enums import SegmentTypeEnum
from models.main import db
from models.nutritional import NutritionalScreening
from models.prescription import Patient
from models.segment import Segment


def get_indicators_data(setor=None, ala=None, start_date=None, end_date=None):
    """Return admitted patients in the period with their first triagem_at."""

    # subquery: earliest completed triage per admission
    first_triagem = (
        db.session.query(
            NutritionalScreening.nratendimento,
            func.min(NutritionalScreening.triagem_at).label("triagem_at"),
        )
        .filter(NutritionalScreening.triagem_at.isnot(None))
        .group_by(NutritionalScreening.nratendimento)
        .subquery("first_triagem")
    )

    query = (
        db.session.query(
            Patient.admissionNumber.label("nratendimento"),
            Patient.admissionDate.label("dtinternacao"),
            first_triagem.c.triagem_at,
        )
        .select_from(Patient)
        .outerjoin(
            SegmentDepartment,
            (SegmentDepartment.idDepartment == Patient.idDepartment)
            & (SegmentDepartment.idHospital == Patient.idHospital),
        )
        .outerjoin(Segment, Segment.id == SegmentDepartment.id)
        .outerjoin(
            Department,
            (Department.id == Patient.idDepartment)
            & (Department.idHospital == Patient.idHospital),
        )
        .outerjoin(
            first_triagem,
            first_triagem.c.nratendimento == Patient.admissionNumber,
        )
        .filter(Patient.idDepartment.isnot(None))
    )

    if start_date is not None:
        query = query.filter(Patient.admissionDate >= start_date)

    if end_date is not None:
        query = query.filter(Patient.admissionDate < end_date)

    if setor is not None:
        query = query.filter(Patient.idDepartment == setor)

    if ala is not None:
        ala_upper = ala.upper()
        if ala_upper == "UTI":
            query = query.filter(Segment.type == SegmentTypeEnum.ICU.value)
        elif ala_upper == "ENFERMARIA":
            query = query.filter(
                or_(
                    Segment.type != SegmentTypeEnum.ICU.value,
                    Segment.type.is_(None),
                )
            )
        else:
            query = query.filter(Segment.description.ilike(f"%{ala}%"))

    return query.all()
