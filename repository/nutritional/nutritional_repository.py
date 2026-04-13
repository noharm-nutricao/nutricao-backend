from models.main import db
from models.nutritional.nutritional import NutritionalTriage

def get_patients_repository():
    #toDO
    pass

def save_manual_mnutric(admission_number: int, mnutric: dict):
    if not _is_nutritional_triage_table_ready():
        return None

    triage = (
        db.session.query(NutritionalTriage)
        .filter(NutritionalTriage.admissionNumber == admission_number)
        .filter(NutritionalTriage.protocol == "MNUTRIC")
        .first()
    )

    if triage is None:
        triage = NutritionalTriage()
        triage.admissionNumber = admission_number
        triage.protocol = "MNUTRIC"
        db.session.add(triage)

    triage.age            = mnutric["age"]
    triage.apache         = mnutric["apache"]
    triage.sofa           = mnutric["sofa"]
    triage.comorbidity    = mnutric["comorbity"]
    triage.days           = mnutric["daysUTI"]
    triage.total          = mnutric["total"]
    triage.apacheManual   = True
    triage.sofaManual     = True
    triage.classification = mnutric["classify"]

    db.session.flush()

    return triage

def get_active_admissions():
    """Return all active admissions with ICU protocol flag.

    Active means dtalta IS NULL. Uses LEFT JOINs on segmentosetor and segmento
    so patients whose sector has no segment mapping are still included
    (is_icu defaults to False via COALESCE).

    Returns:
        List of rows with fields:
            nratendimento, fksetor, dtnascimento, dtinternacao,
            peso, altura, idcid, tp_segmento (int|None), is_icu (bool)
    """
    query = text(
        """
        SELECT
            p.nratendimento,
            p.fksetor,
            p.dtnascimento,
            p.dtinternacao,
            p.peso,
            p.altura,
            p.idcid,
            seg.tp_segmento,
            COALESCE(seg.tp_segmento = :icu_type, false) AS is_icu
        FROM pessoa p
        LEFT JOIN segmentosetor ss  ON ss.fksetor     = p.fksetor
        LEFT JOIN segmento seg      ON seg.idsegmento  = ss.fksegmento
        WHERE p.dtalta IS NULL
        """
    )
    result = db.session.execute(query, {"icu_type": SegmentTypeEnum.ICU.value})
    return result.fetchall()

def get_active_admissions():
    """Return all active admissions with ICU protocol flag.

    Active means dtalta IS NULL. Uses LEFT JOINs on segmentosetor and segmento
    so patients whose sector has no segment mapping are still included
    (is_icu defaults to False via COALESCE).

    Returns:
        List of rows with fields:
            nratendimento, fksetor, dtnascimento, dtinternacao,
            peso, altura, idcid, tp_segmento (int|None), is_icu (bool)
    """
    query = text(
        """
        SELECT
            p.nratendimento,
            p.fksetor,
            p.dtnascimento,
            p.dtinternacao,
            p.peso,
            p.altura,
            p.idcid,
            seg.tp_segmento,
            COALESCE(seg.tp_segmento = :icu_type, false) AS is_icu
        FROM pessoa p
        LEFT JOIN segmentosetor ss  ON ss.fksetor     = p.fksetor
        LEFT JOIN segmento seg      ON seg.idsegmento  = ss.fksegmento
        WHERE p.dtalta IS NULL
        """
    )
    result = db.session.execute(query, {"icu_type": SegmentTypeEnum.ICU.value})
    return result.fetchall()

# Verify if we have the triagem table and their columns
def _is_nutritional_triage_table_ready() -> bool:
    connection = db.session.connection()
    schema = connection.get_execution_options().get("schema_translate_map", {}).get(None) or "demo"

    table_exists = bool(
        db.session.execute(
            text(
                "SELECT EXISTS ("
                "    SELECT 1 FROM information_schema.tables "
                "    WHERE table_schema = :schema "
                "      AND table_name = 'nutricional_triagem'"
                ")"
            ),
            {"schema": schema},
        ).scalar()
    )

    if not table_exists:
        return False

    required_columns = {
        "id",
        "nratendimento",
        "protocolo",
        "mn_idade",
        "mn_apache",
        "mn_sofa",
        "mn_comor",
        "mn_dias",
        "mn_total",
        "mn_apache_manual",
        "mn_sofa_manual",
        "classificacao",
    }
    existing_columns = {
        row[0]
        for row in db.session.execute(
            text(
                "SELECT column_name "
                "FROM information_schema.columns "
                "WHERE table_schema = :schema "
                "  AND table_name = 'nutricional_triagem'"
            ),
            {"schema": schema},
        ).all()
    }

    return required_columns.issubset(existing_columns)