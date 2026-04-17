"""Repository for nutritional patients listing query."""

from sqlalchemy import case, extract, func, literal, or_, text

from models.appendix import Department, SegmentDepartment
from models.enums import SegmentTypeEnum
from models.main import db
from models.nutritional import (
    NutritionalScreening,
    NutritionalD7,
    NutritionalGlim,
)
from models.prescription import Patient
from models.segment import Segment


def get_patients(setor=None, ala=None):
    """Return active admissions with basic patient data for nutrition module."""

    # Derive ala label from segment type
    ala_label = case(
        (Segment.type == SegmentTypeEnum.ICU.value, literal("UTI")),
        else_=literal("Enfermaria"),
    ).label("ala")

    # haval
    haval_subq = (
        db.session.query(func.max(NutritionalScreening.created_at))
        .filter(NutritionalScreening.nratendimento == Patient.admissionNumber)
        .correlate(Patient)
        .scalar_subquery()
    )

    haval_expr = (
        extract("epoch", func.now() - haval_subq) / 3600.0
    ).label("haval")

    # d7
    d7_subq = (
        db.session.query(func.count())
        .filter(NutritionalD7.nratendimento == Patient.admissionNumber)
        .filter(NutritionalD7.concluido.is_(False))
        .filter(
            NutritionalD7.dt_prevista
            <= func.now() + text("interval '48 hours'")
        )
        .correlate(Patient)
        .scalar_subquery()
    )

    d7_expr = (d7_subq > 0).label("d7")

    # sev
    sev_subq = (
        db.session.query(NutritionalScreening.classificacao)
        .filter(NutritionalScreening.nratendimento == Patient.admissionNumber)
        .correlate(Patient)
        .order_by(NutritionalScreening.created_at.desc())
        .limit(1)
        .scalar_subquery()
    ).label("sev")

    # GLIM
    glim_diag_subq = (
        db.session.query(NutritionalGlim.diagnostico)
        .filter(NutritionalGlim.nratendimento == Patient.admissionNumber)
        .correlate(Patient)
        .order_by(NutritionalGlim.created_at.desc())
        .limit(1)
        .scalar_subquery()
    ).label("glim_diag")

    glim_fen_subq = (
        db.session.query(NutritionalGlim.fenotipos)
        .filter(NutritionalGlim.nratendimento == Patient.admissionNumber)
        .correlate(Patient)
        .order_by(NutritionalGlim.created_at.desc())
        .limit(1)
        .scalar_subquery()
    ).label("glim_fen")

    glim_etiol_subq = (
        db.session.query(NutritionalGlim.etiologias)
        .filter(NutritionalGlim.nratendimento == Patient.admissionNumber)
        .correlate(Patient)
        .order_by(NutritionalGlim.created_at.desc())
        .limit(1)
        .scalar_subquery()
    ).label("glim_etiol")

    query = (
        db.session.query(
            Patient.admissionNumber.label("id"),
            Patient.bed.label("leito"),
            ala_label,
            Patient.idDepartment.label("fksetor"),
            Department.name.label("nome_setor"),
            Segment.type.label("tp_segmento"),
            Patient.admissionDate.label("dtinternacao"),
            Patient.birthdate.label("dtnascimento"),
            Patient.weight.label("peso"),
            Patient.height.label("altura"),
            Patient.id_icd.label("idcid"),
            haval_expr,
            d7_expr,
            sev_subq,
            glim_diag_subq,
            glim_fen_subq,
            glim_etiol_subq,
        )
        .select_from(Patient)
        .join(
            SegmentDepartment,
            (SegmentDepartment.idDepartment == Patient.idDepartment)
            & (SegmentDepartment.idHospital == Patient.idHospital),
        )
        .join(
            Segment,
            Segment.id == SegmentDepartment.id,
        )
        .join(
            Department,
            (Department.id == Patient.idDepartment)
            & (Department.idHospital == Patient.idHospital),
        )
        .filter(Patient.dischargeDate.is_(None))
    )

    # filtros
    if setor is not None:
        query = query.filter(Patient.idDepartment == setor)

    if ala is not None:
        ala = ala.upper()

        if ala == "UTI":
            query = query.filter(Segment.type == SegmentTypeEnum.ICU.value)

        elif ala == "ENFERMARIA":
            query = query.filter(
                or_(
                    Segment.type != SegmentTypeEnum.ICU.value,
                    Segment.type.is_(None),
                )
            )

        else:
            query = query.filter(Segment.type.is_(None))

    return query.all()