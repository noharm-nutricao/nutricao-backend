"""Nutritional repository.

Data access layer for the nutritional module. Queries the NoHarm schema
tables (pessoa, segmentosetor, segmento) to retrieve patient data needed
for nutritional score calculations.
"""

from sqlalchemy import text

from models.enums import SegmentTypeEnum
from models.main import db


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
