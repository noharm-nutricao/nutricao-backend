"""Repository for nutritional patients listing query."""

from sqlalchemy import case, extract, func, literal, or_, text

from models.appendix import Department, SegmentDepartment
from models.enums import SegmentTypeEnum
from models.main import db
from models.nutritional import (
    NutritionalAssessment,
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
        else_=Segment.description,
    ).label("ala")

    # haval
    haval_subq = (
        db.session.query(func.max(NutritionalAssessment.created_at))
        .filter(NutritionalAssessment.nratendimento == Patient.admissionNumber)
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

    # freq
    last_assessment = (
        db.session.query(
            NutritionalAssessment.nratendimento,
            NutritionalAssessment.frequencia,
            func.max(NutritionalAssessment.created_at),
        )
        .distinct(NutritionalAssessment.nratendimento)
        .group_by(
            NutritionalAssessment.nratendimento,
            NutritionalAssessment.frequencia,
        )
        .subquery("last_assessment")
    )
    
    # sev
    sev_subq = (
        db.session.query(NutritionalScreening.classificacao)
        .filter(NutritionalScreening.nratendimento == Patient.admissionNumber)
        .correlate(Patient)
        .order_by(NutritionalScreening.id.desc())
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

    # campo1 — NRS-2002 score fields from latest NRS2002 screening row
    nrs_data_subq = (
        db.session.query(
            func.json_build_object(
                "nrs_total", NutritionalScreening.nrs_total,
                "nrs_nut", NutritionalScreening.nrs_nut,
                "nrs_doenca", NutritionalScreening.nrs_doenca,
                "nrs_idade", NutritionalScreening.nrs_idade,
            )
        )
        .filter(NutritionalScreening.nratendimento == Patient.admissionNumber)
        .filter(NutritionalScreening.protocolo == "NRS2002")
        .correlate(Patient)
        .order_by(NutritionalScreening.id.desc())
        .limit(1)
        .scalar_subquery()
    ).label("nrs_data")

    # campo1 — mNUTRIC score fields from latest MNUTRIC screening row
    mnutric_data_subq = (
        db.session.query(
            func.json_build_object(
                "mn_total", NutritionalScreening.mn_total,
                "mn_idade", NutritionalScreening.mn_idade,
                "mn_apache", NutritionalScreening.mn_apache,
                "mn_sofa", NutritionalScreening.mn_sofa,
                "mn_comor", NutritionalScreening.mn_comor,
                "mn_dias", NutritionalScreening.mn_dias,
                "mn_apache_manual", NutritionalScreening.mn_apache_manual,
                "mn_sofa_manual", NutritionalScreening.mn_sofa_manual,
            )
        )
        .filter(NutritionalScreening.nratendimento == Patient.admissionNumber)
        .filter(NutritionalScreening.protocolo == "MNUTRIC")
        .correlate(Patient)
        .order_by(NutritionalScreening.id.desc())
        .limit(1)
        .scalar_subquery()
    ).label("mnutric_data")

    query = (
        db.session.query(
            Patient.admissionNumber.label("id"),
            last_assessment.c.frequencia.label("freq_horas"),
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
            nrs_data_subq,
            mnutric_data_subq,
        )
        .select_from(Patient)
        .outerjoin(
            last_assessment,
            last_assessment.c.nratendimento == Patient.admissionNumber,
        )
        .outerjoin(
            SegmentDepartment,
            (SegmentDepartment.idDepartment == Patient.idDepartment)
            & (SegmentDepartment.idHospital == Patient.idHospital),
        )
        .outerjoin(
            Segment,
            Segment.id == SegmentDepartment.id,
        )
        .outerjoin(
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