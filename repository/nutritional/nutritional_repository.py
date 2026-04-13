from models.main import db
from models.nutritional.nutritional import NutritionalTriage

def get_patients_repository():
    #toDO
    pass


def _ensure_nutritional_triage_table():
    connection = db.session.connection()
    NutritionalTriage.__table__.create(bind=connection, checkfirst=True)

    schema = connection.get_execution_options().get("schema_translate_map", {}).get(None)
    table_name = f"{schema}.nutricional_triagem" if schema else "nutricional_triagem"

    connection.execute(
        text(
            f"ALTER TABLE {table_name} "
            "ADD COLUMN IF NOT EXISTS mn_total INTEGER"
        )
    )


def save_manual_mnutric(admission_number: int, apache: int, sofa: int, total: int | None = None):
    _ensure_nutritional_triage_table()

    triage = (
        db.session.query(NutritionalTriage)
        .filter(NutritionalTriage.admissionNumber == admission_number)
        .first()
    )

    if triage is None:
        triage = NutritionalTriage()
        triage.admissionNumber = admission_number
        db.session.add(triage)

    triage.apache = apache
    triage.sofa = sofa
    triage.total = total
    triage.apacheManual = True
    triage.sofaManual = True

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
