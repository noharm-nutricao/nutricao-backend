"""Repository for nutritional patients listing query."""

from sqlalchemy import case, extract, func, literal
from sqlalchemy.dialects.postgresql import INTERVAL

from models.appendix import Department, SegmentDepartment
from models.enums import SegmentTypeEnum
from models.main import db
from models.nutritional import (
    NutritionalScreening,
    NutritionalD7,
    NutritionalGlim,
    NutritionalTriagem,
)
from models.prescription import Patient
from models.segment import Segment


def get_patients(setor=None, ala=None):
    """Return active admissions with basic patient data for nutrition module.

    Args:
        setor: Optional department id filter.
        ala: Optional ward type filter ('UTI' or other).

    Returns:
        List of result rows with patient and derived nutritional fields.
    """

    # Derive ala label from segment type: ICU (3) = UTI, else 'Enfermaria'
    ala_label = case(
        (Segment.type == SegmentTypeEnum.ICU.value, literal("UTI")),
        else_=literal("Enfermaria"),
    ).label("ala")

    # haval: hours since the last nutritional evaluation (correlated subquery)
    haval_subq = (
        db.session.query(
            func.max(NutritionalScreening.created_at)
        )
        .filter(NutritionalScreening.nratendimento == Patient.admissionNumber)
        .correlate(Patient)
        .scalar_subquery()
    )

    haval_expr = (
        extract("epoch", func.now() - haval_subq) / 3600.0
    ).label("haval")

    # d7: true when at least one active D7 with dt_prevista <= NOW() + 48h
    d7_subq = (
        db.session.query(func.count())
        .filter(NutritionalD7.nratendimento == Patient.admissionNumber)
        .filter(NutritionalD7.concluido == False)
        .filter(
            NutritionalD7.dt_prevista
            <= func.now() + func.cast("48 hours", INTERVAL)
        )
        .correlate(Patient)
        .scalar_subquery()
    )

    d7_expr = (d7_subq > 0).label("d7")

# !! REMOVIDO SEM SENTIDO NO DIA 16/04 !!

    # # conduta: last registered conduct
    # conduta_subq = (
    #     db.session.query(NutritionalScreening.conduta)
    #     .filter(NutritionalScreening.nratendimento == Patient.admissionNumber)
    #     .correlate(Patient)
    #     .order_by(NutritionalScreening.created_at.desc())
    #     .limit(1)
    #     .scalar_subquery()
    # ).label("conduta")

    # sev: severity classification from latest triage
    sev_subq = (
        db.session.query(NutritionalScreening.classificacao)
        .filter(NutritionalScreening.nratendimento == Patient.admissionNumber)
        .correlate(Patient)
        .order_by(NutritionalScreening.created_at.desc())
        .limit(1)
        .scalar_subquery()
    ).label("sev")

    # GLIM diagnosis fields
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
            # conduta_subq,
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

    if setor is not None:
        query = query.filter(Patient.idDepartment == setor)

    if ala is not None:
        if ala.upper() == "UTI":
            query = query.filter(Segment.type == SegmentTypeEnum.ICU.value)
        elif ala.upper() == "ENFERMARIA":
            query = query.filter(Segment.type != SegmentTypeEnum.ICU.value)
        else:
            query = query.filter(Segment.type == None)

    return query.all()
