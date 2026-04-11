"""Nutritional repository.

Data access layer for the nutritional module. Queries the NoHarm schema
tables (pessoa, segmentosetor, segmento) to retrieve patient data needed
for nutritional score calculations.
"""

import re

from sqlalchemy import text

from models.enums import SegmentTypeEnum
from models.main import db

_SAFE_SCHEMA_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def get_active_admissions(schema: str):
    """Return all active admissions with ICU protocol flag for a given schema.

    Active means dtalta IS NULL. Uses LEFT JOINs on segmentosetor and segmento
    so patients whose sector has no segment mapping are still included
    (is_icu defaults to False via COALESCE).

    Args:
        schema: PostgreSQL schema name to query (e.g. "demo")

    Returns:
        List of rows with fields:
            nratendimento, fksetor, dtnascimento, dtinternacao,
            peso, altura, idcid, tp_segmento (int|None), is_icu (bool)
    """
    if not _SAFE_SCHEMA_RE.match(schema):
        raise ValueError(f"Invalid schema name: {schema!r}")

    query = text(
        f"""
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
        FROM {schema}.pessoa p
        LEFT JOIN {schema}.segmentosetor ss  ON ss.fksetor    = p.fksetor
        LEFT JOIN {schema}.segmento seg      ON seg.idsegmento = ss.idsegmento
        WHERE p.dtalta IS NULL
        """
    )
    result = db.session.execute(query, {"icu_type": SegmentTypeEnum.ICU.value})
    return result.fetchall()
