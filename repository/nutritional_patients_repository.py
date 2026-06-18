"""Repository for nutritional patients listing query."""

from sqlalchemy import case, extract, func, literal, or_, text

from models.appendix import Department, SegmentDepartment
from models.enums import SegmentTypeEnum
from models.main import db, User
from models.nutritional import (
    NutritionalAlert,
    NutritionalAssessment,
    NutritionalD7,
    NutritionalGlim,
    NutritionalScreening,
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

    # freq_horas
    freq_map = case(
        (NutritionalAssessment.frequencia == "12h", 12),
        (NutritionalAssessment.frequencia == "24h", 24),
        (NutritionalAssessment.frequencia == "48h", 48),
        (NutritionalAssessment.frequencia == "7d", 168),
        else_=None,
    )

    last_assessment = (
        db.session.query(
            NutritionalAssessment.nratendimento,
            freq_map.label("freq_horas"),
        )
        .distinct(NutritionalAssessment.nratendimento)
        .order_by(
            NutritionalAssessment.nratendimento,
            NutritionalAssessment.created_at.desc(),
            NutritionalAssessment.id.desc(),
        )
        .subquery("last_assessment")
    )
    # sev - filter by protocol based on segment type (ICU -> MNUTRIC, else NRS2002)
    _sev_protocolo = case(
        (Segment.type == SegmentTypeEnum.ICU.value, literal("MNUTRIC")),
        else_=literal("NRS2002"),
    )
    sev_subq = (
        db.session.query(NutritionalScreening.classificacao)
        .filter(NutritionalScreening.nratendimento == Patient.admissionNumber)
        .filter(NutritionalScreening.protocolo == _sev_protocolo)
        .correlate(Patient, Segment)
        .order_by(NutritionalScreening.id.desc())
        .limit(1)
        .scalar_subquery()
    ).label("sev")

    # score total (NRS-2002)
    nrs_total_subq = (
        db.session.query(NutritionalScreening.nrs_total)
        .filter(NutritionalScreening.nratendimento == Patient.admissionNumber)
        .filter(NutritionalScreening.protocolo == "NRS2002")
        .correlate(Patient)
        .order_by(NutritionalScreening.id.desc())
        .limit(1)
        .scalar_subquery()
    )

    # score total (mNUTRIC)
    mnutric_total_subq = (
        db.session.query(NutritionalScreening.mn_total)
        .filter(NutritionalScreening.nratendimento == Patient.admissionNumber)
        .filter(NutritionalScreening.protocolo == "MNUTRIC")
        .correlate(Patient)
        .order_by(NutritionalScreening.id.desc())
        .limit(1)
        .scalar_subquery()
    )

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
                "nrs_completo", NutritionalScreening.nrs_completo,
                "calculado_at", NutritionalScreening.calculado_at,
                "created_at", NutritionalScreening.created_at,
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

    conduta_subq = (
        db.session.query(NutritionalAssessment.conduta)
        .filter(NutritionalAssessment.nratendimento == Patient.admissionNumber)
        .correlate(Patient)
        .order_by(
            NutritionalAssessment.created_at.desc(),
            NutritionalAssessment.id.desc(),
        )
        .limit(1)
        .scalar_subquery()
    ).label("conduta")

    hist_inner = (
        db.session.query(
            func.json_build_object(
                "h", func.to_char(NutritionalAssessment.created_at, "DD/MM HH24:MI"),
                "p", User.name,
                "c", NutritionalAssessment.conduta,
                "freq", NutritionalAssessment.frequencia,
                "ing", NutritionalAssessment.ingestao,
            ).label("item")
        )
        .select_from(NutritionalAssessment)
        .outerjoin(User, User.id == NutritionalAssessment.idusuario)
        .filter(NutritionalAssessment.nratendimento == Patient.admissionNumber)
        .correlate(Patient)
        .order_by(
            NutritionalAssessment.created_at.desc(),
            NutritionalAssessment.id.desc(),
        )
        .limit(10)
        .subquery("hist_inner")
    )

    hist_agg_subq = (
        db.session.query(func.json_agg(hist_inner.c.item))
        .select_from(hist_inner)
        .scalar_subquery()
    ).label("hist")

    inst_inner = (
        db.session.query(
            func.json_build_object(
                "id", NutritionalAlert.id,
                "t", NutritionalAlert.tipo,
                "d", NutritionalAlert.descricao,
                "sev", NutritionalAlert.severidade,
                "al_ok", NutritionalAlert.reconhecido,
            ).label("item")
        )
        .select_from(NutritionalAlert)
        .filter(NutritionalAlert.nratendimento == Patient.admissionNumber)
        .filter(NutritionalAlert.ativo == True)
        .filter(NutritionalAlert.reconhecido == False)
        .correlate(Patient)
        .order_by(NutritionalAlert.created_at.desc())
        .subquery("inst_inner")
    )

    inst_subq = (
        db.session.query(func.json_agg(inst_inner.c.item))
        .select_from(inst_inner)
        .scalar_subquery()
    ).label("inst")

    query = (
        db.session.query(
            Patient.admissionNumber.label("id"),
            last_assessment.c.freq_horas,
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
            conduta_subq,
            hist_agg_subq,
            inst_subq,
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

    sev_order = case(
        (sev_subq == literal("cr"), 1),
        (sev_subq == literal("al"), 2),
        (sev_subq == literal("md"), 3),
        (sev_subq == literal("bx"), 4),
        else_=5,
    )

    score_expr = case(
        (
            Segment.type == SegmentTypeEnum.ICU.value,
            func.coalesce(mnutric_total_subq, nrs_total_subq),
        ),
        else_=nrs_total_subq,
    )

    is_icu_expr = case(
        (Segment.type == SegmentTypeEnum.ICU.value, 1),
        else_=0,
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

    query = query.order_by(
        sev_order,
        score_expr.desc().nulls_last(),
        d7_expr.desc(),
        haval_expr.desc().nulls_last(),
        is_icu_expr.desc(),
        Patient.admissionDate.asc().nulls_last(),
        Patient.admissionNumber.asc(),
    )
    return query.all()